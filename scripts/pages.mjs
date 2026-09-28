import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const json = (value) => JSON.stringify(value, null, '\t') + '\n';
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

export function validate(data) {
	if (!object(data) || !Object.keys(data).length) throw new Error('Empty or invalid dataset');
	const result = {};
	for (const year of Object.keys(data).sort()) {
		if (!/^2\d{3}$/.test(year) || !object(data[year]) || !Object.keys(data[year]).length) {
			throw new Error(`Invalid year: ${year}`);
		}
		result[year] = {};
		for (const date of Object.keys(data[year]).sort()) {
			if (
				!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
				!date.startsWith(`${year}-`) ||
				!Number.isFinite(Date.parse(`${date}T00:00:00Z`)) ||
				new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) !== date
			) throw new Error(`Invalid date: ${date}`);
			const names = data[year][date];
			if (
				!Array.isArray(names) || !names.length || names.length !== new Set(names).size ||
				names.some((name) => typeof name !== 'string' || !name.trim() ||
					name.length > 200 || /[\u0000-\u001f\u007f]/u.test(name))
			) throw new Error(`Invalid names: ${date}`);
			result[year][date] = names;
		}
	}
	return result;
}

export async function readDatasets(directory) {
	const read = async (path) => validate(JSON.parse(await readFile(join(directory, path), 'utf8')));
	return {
		holidays: await read('basic.json'),
		anniversaries: await read('anniversaries/basic.json'),
	};
}

// Preserve existing event UIDs so subscriptions do not duplicate old events.
const uid = (date, name) =>
	`${date.replaceAll('-', '')}-${createHash('md5').update(name).digest('hex')}`;
const escapeICS = (value) => value.replaceAll('\\', '\\\\').replaceAll(';', '\\;').replaceAll(',', '\\,');
const escapeCSV = (value) => `"${value.replaceAll('"', '""')}"`;

export function foldLine(line) {
	let output = '';
	let length = 0;
	for (const char of line) {
		const bytes = Buffer.byteLength(char);
		if (length + bytes > 75) {
			output += '\r\n ';
			length = 1;
		}
		output += char;
		length += bytes;
	}
	return output;
}

export function calendar(preset, name, timestamp) {
	const stamp = new Date(timestamp).toISOString().replace(/[-:]/g, '').slice(0, 15) + 'Z';
	const lines = [
		'BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//holidays-kr fork//KO',
		'CALSCALE:GREGORIAN', `X-WR-CALNAME:${name}`, 'X-WR-TIMEZONE:Asia/Seoul',
	];
	for (const [date, names] of Object.entries(preset)) {
		const end = new Date(`${date}T00:00:00Z`);
		end.setUTCDate(end.getUTCDate() + 1);
		for (const subject of names) {
			lines.push(
				'BEGIN:VEVENT', `DTSTART;VALUE=DATE:${date.replaceAll('-', '')}`,
				`DTEND;VALUE=DATE:${end.toISOString().slice(0, 10).replaceAll('-', '')}`,
				`DTSTAMP:${stamp}`, `UID:${uid(date, subject)}`, `SUMMARY:${escapeICS(subject)}`,
				'CLASS:PUBLIC', 'TRANSP:TRANSPARENT', 'END:VEVENT',
			);
		}
	}
	lines.push('END:VCALENDAR');
	return lines.map(foldLine).join('\r\n') + '\r\n';
}

export async function writeDatasets(directory, datasets, timestamp) {
	for (const [kind, data] of Object.entries(datasets)) {
		const dir = kind === 'holidays' ? directory : join(directory, 'anniversaries');
		const name = kind === 'holidays' ? '대한민국의 공휴일' : '대한민국의 기념일';
		await mkdir(dir, { recursive: true });
		await writeFile(join(dir, 'basic.json'), json(data));
		await writeFile(join(dir, 'basic.ics'), calendar(Object.assign({}, ...Object.values(data)), name, timestamp));
		for (const [year, preset] of Object.entries(data)) {
			await writeFile(join(dir, `${year}.json`), json(preset));
			await writeFile(join(dir, `${year}.ics`), calendar(preset, name, timestamp));
			const rows = Object.entries(preset).flatMap(([date, names]) =>
				names.map((subject) => `${date},${escapeCSV(subject)}`));
			await writeFile(join(dir, `${year}.csv`), '\ufeffStart date,Subject\r\n' + rows.join('\r\n') + '\r\n');
		}
	}
}

export async function sync(upstream, repository = root) {
	const current = await readDatasets(join(repository, 'public'));
	const next = await readDatasets(upstream);
	// A truncated upstream snapshot must never silently remove a supported year.
	for (const kind of Object.keys(current)) {
		for (const year of Object.keys(current[kind])) {
			if (!next[kind][year]) throw new Error(`Upstream removed ${kind}/${year}`);
		}
	}
	if (json(current) === json(next)) return false;
	await writeDatasets(join(repository, 'public'), next, new Date());
	// Keep the existing npm API's local presets consistent with the Pages snapshot.
	await mkdir(join(repository, 'src/holidays'), { recursive: true });
	for (const [year, preset] of Object.entries(next.holidays)) {
		await writeFile(join(repository, `src/holidays/${year}.ts`), `export default ${json(preset).trim()} as const;\n`);
	}
	await writeFile(join(repository, 'src/holidays/all.ts'),
		Object.keys(next.holidays).map((year) => `export { default as y${year} } from './${year}.ts';`).join('\n') + '\n');
	await writeFile(join(repository, 'src/anniversaries.ts'),
		Object.entries(next.anniversaries).map(([year, preset]) =>
			`export const y${year} = ${json(preset).trim()} as const;\n`).join('\n'));
	return true;
}

export async function build(repository = root, output = join(repository, '_site')) {
	const datasets = await readDatasets(join(repository, 'public'));
	// Reproducible output: unrelated code commits do not change event timestamps.
	const seconds = execFileSync('git', ['log', '-1', '--format=%ct', '--', 'public'], {
		cwd: repository, encoding: 'utf8',
	}).trim();
	if (!/^\d+$/.test(seconds)) throw new Error('No committed public snapshot');
	await writeDatasets(output, datasets, Number(seconds) * 1000);
	await writeFile(join(output, '.nojekyll'), '');
	const cname = await readFile(join(repository, 'CNAME'), 'utf8').catch((error) => {
		if (error.code === 'ENOENT') return null;
		throw error;
	});
	if (cname !== null) {
		if (!/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(cname.trim())) {
			throw new Error('Invalid custom domain in CNAME');
		}
		await writeFile(join(output, 'CNAME'), cname.trim() + '\n');
	}
	await writeFile(join(output, 'status.json'), json({
		schemaVersion: 1,
		dataUpdatedAt: new Date(Number(seconds) * 1000).toISOString(),
		years: Object.keys(datasets.holidays),
		digest: createHash('sha256').update(json(datasets)).digest('hex'),
	}));
	const sections = Object.entries(datasets).map(([kind, data]) => {
		const prefix = kind === 'holidays' ? './' : './anniversaries/';
		const label = kind === 'holidays' ? '공휴일' : '기념일';
		return `<section><h2>${label}</h2><p>전체 연도: <a href="${prefix}basic.json">JSON</a> · <a href="${prefix}basic.ics">캘린더 구독 (ICS)</a></p><ul>${
			Object.keys(data).map((year) => `<li>${year}년: ${
				['json', 'csv', 'ics'].map((ext) => `<a href="${prefix}${year}.${ext}">${ext.toUpperCase()}</a>`).join(' · ')
			}</li>`).join('')
		}</ul></section>`;
	}).join('');
	await writeFile(join(output, 'index.html'), `<!doctype html>
<html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>대한민국 공휴일 · 독립 호스팅</title>
<style>body{font:1rem/1.7 system-ui,sans-serif;max-width:48rem;margin:3rem auto;padding:0 1rem}a{color:#0759b5}li{margin:.3rem 0}</style>
<h1>대한민국의 공휴일</h1><p>이 사이트의 정적 파일만으로 조회할 수 있습니다. API 키나 외부 CDN은 필요하지 않습니다.</p>
<p>캘린더 앱에 ICS 링크 주소를 복사해 구독하세요. 기념일은 공휴일과 별도입니다.</p>
${sections}<p><a href="./status.json">데이터 상태</a> · 원본: hyunbinseo/holidays-kr (MIT)</p></html>
`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const command = process.argv[2];
	if (command === 'build') await build();
	else if (command === 'sync' && process.argv[3]) {
		console.log(await sync(resolve(process.argv[3])) ? 'Data updated' : 'Already up to date');
	} else throw new Error('Usage: node scripts/pages.mjs build | sync <upstream-public-directory>');
}
