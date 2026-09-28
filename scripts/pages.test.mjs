import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { build, calendar, foldLine, readDatasets, sync, validate, writeDatasets } from './pages.mjs';

const data = {
	holidays: { '2026': { '2026-01-01': ['1월 1일'] } },
	anniversaries: { '2026': { '2026-05-08': ['어버이 날'] } },
};
const stamp = '2026-01-01T00:00:00Z';

async function fixture(t) {
	const directory = await mkdtemp(join(tmpdir(), 'holidays-pages-'));
	t.after(() => rm(directory, { recursive: true, force: true }));
	return directory;
}

test('validates, sorts, and rejects malformed or empty data', () => {
	assert.deepEqual(validate(data.holidays), data.holidays);
	for (const input of [
		{}, [], null, { '2026': {} }, { '2026': { '2026-02-29': ['bad'] } },
		{ '2026': { '2027-01-01': ['bad'] } }, { '2026': { '2026-01-01': [] } },
		{ '2026': { '2026-01-01': ['x', 'x'] } }, { '2026': { '2026-01-01': ['x\nBEGIN:VEVENT'] } },
		{ '2026': { '2026-01-01': [42] } }, { '2026': { '2026-01-01': [' '] } },
	]) assert.throws(() => validate(input));
	assert.deepEqual(validate({ '2028': { '2028-02-29': ['윤일'] } }), { '2028': { '2028-02-29': ['윤일'] } });
});

test('ICS retains upstream UIDs, escapes text and has exclusive end dates', () => {
	const ics = calendar({ '2026-01-01': ['1월 1일'], '2026-12-31': ['가,나;다\\라'] }, '공휴일', stamp);
	assert.match(ics, /UID:20260101-fbe3d03c43fb47f8f07196897b886d23\r\n/);
	assert.match(ics, /DTEND;VALUE=DATE:20270101\r\n/);
	assert.ok(ics.includes('SUMMARY:가\\,나\\;다\\\\라\r\n'));
	assert.ok(ics.endsWith('END:VCALENDAR\r\n'));
	assert.equal(ics.replaceAll('\r\n', '').includes('\n'), false);
});

test('ICS folds UTF-8 lines without splitting multibyte characters', () => {
	const original = 'SUMMARY:' + '대한민국'.repeat(30);
	const folded = foldLine(original);
	assert.equal(folded.replaceAll('\r\n ', ''), original);
	for (const line of folded.split('\r\n')) assert.ok(Buffer.byteLength(line) <= 75);
});

test('writes all formats with quoted CSV and separate anniversaries', async (t) => {
	const directory = await fixture(t);
	const datasets = structuredClone(data);
	datasets.holidays['2026']['2026-01-02'] = ['쉼표,따옴표"'];
	await writeDatasets(directory, datasets, stamp);
	assert.deepEqual(await readDatasets(directory), datasets);
	const csv = await readFile(join(directory, '2026.csv'), 'utf8');
	assert.ok(csv.includes('2026-01-02,"쉼표,따옴표"""\r\n'));
	assert.deepEqual(JSON.parse(await readFile(join(directory, '2026.json'), 'utf8')), datasets.holidays['2026']);
	assert.ok((await readFile(join(directory, 'anniversaries/basic.ics'), 'utf8')).includes('어버이 날'));
});

test('sync is idempotent and never executes upstream code', async (t) => {
	const directory = await fixture(t);
	const upstream = join(directory, 'upstream');
	const repository = join(directory, 'fork');
	await writeDatasets(upstream, data, stamp);
	await writeDatasets(join(repository, 'public'), data, stamp);
	await writeFile(join(upstream, 'payload.ts'), 'throw new Error("must never execute")');
	const original = await readFile(join(repository, 'public/basic.ics'), 'utf8');
	assert.equal(await sync(upstream, repository), false);
	assert.equal(await readFile(join(repository, 'public/basic.ics'), 'utf8'), original);
	const next = structuredClone(data);
	next.holidays['2027'] = { '2027-01-01': ['1월 1일'] };
	await writeDatasets(upstream, next, stamp);
	assert.equal(await sync(upstream, repository), true);
	assert.deepEqual(await readDatasets(join(repository, 'public')), next);
	assert.ok((await readFile(join(repository, 'src/holidays/all.ts'), 'utf8')).includes('y2027'));
	assert.ok((await readFile(join(repository, 'src/holidays/2027.ts'), 'utf8')).includes('2027-01-01'));
	assert.equal(await sync(upstream, repository), false);
});

test('rejects missing years and invalid snapshots before modifying local data', async (t) => {
	const directory = await fixture(t);
	const upstream = join(directory, 'upstream');
	const repository = join(directory, 'fork');
	await writeDatasets(join(repository, 'public'), data, stamp);
	const missing = structuredClone(data);
	missing.holidays = { '2027': { '2027-01-01': ['1월 1일'] } };
	await writeDatasets(upstream, missing, stamp);
	await assert.rejects(sync(upstream, repository), /removed/);
	await writeFile(join(upstream, 'basic.json'), '{"2026":{"2026-02-30":["bad"]}}');
	await assert.rejects(sync(upstream, repository), /Invalid date/);
	assert.deepEqual(await readDatasets(join(repository, 'public')), data);
});

test('offline build is reproducible and generates project-relative links and status', async (t) => {
	const repository = await fixture(t);
	await writeDatasets(join(repository, 'public'), data, stamp);
	await writeFile(join(repository, 'CNAME'), 'holidays.hegelty.me\n');
	const git = (...args) => execFileSync('git', args, { cwd: repository, stdio: 'pipe' });
	git('init');
	git('add', 'public');
	git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture');
	const output = join(repository, '_site');
	await build(repository, output);
	const ics = await readFile(join(output, 'basic.ics'), 'utf8');
	const status = await readFile(join(output, 'status.json'), 'utf8');
	await build(repository, output);
	assert.equal(await readFile(join(output, 'basic.ics'), 'utf8'), ics);
	assert.equal(await readFile(join(output, 'status.json'), 'utf8'), status);
	const html = await readFile(join(output, 'index.html'), 'utf8');
	assert.ok(html.includes('href="./basic.ics"'));
	assert.ok(html.includes('href="./anniversaries/2026.json"'));
	assert.ok(!html.includes('<script'));
	assert.deepEqual(JSON.parse(status).years, ['2026']);
	assert.ok((await readdir(output)).includes('.nojekyll'));
	assert.equal(await readFile(join(output, 'CNAME'), 'utf8'), 'holidays.hegelty.me\n');
});

test('checked-in holiday and anniversary snapshots are valid', async () => {
	const datasets = await readDatasets(new URL('../public/', import.meta.url).pathname);
	assert.ok(Object.keys(datasets.holidays).length >= 10);
});
