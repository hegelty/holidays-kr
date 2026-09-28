import type { Presets } from '#src/types.ts';

// Package generation stays offline. Direct API collection happens separately.
export const checkHolidays = async (presets: Presets) => {
	for (const [y2XXX, preset] of Object.entries(presets)) {
		const yyyy = y2XXX.slice(1);
		if (!/^2\d{3}$/.test(yyyy) || !Object.keys(preset).length) {
			throw new Error(`Invalid or empty year: ${yyyy}`);
		}
		for (const [date, names] of Object.entries(preset)) {
			const timestamp = Date.parse(`${date}T00:00:00Z`);
			if (
				!/^\d{4}-\d{2}-\d{2}$/.test(date) ||
				!date.startsWith(`${yyyy}-`) ||
				!Number.isFinite(timestamp) ||
				new Date(timestamp).toISOString().slice(0, 10) !== date
			) throw new Error(`Invalid date: ${date}`);
			if (
				!names || !names.length || names.length !== new Set(names).size ||
				names.some((name) => typeof name !== 'string' || !name.trim())
			) throw new Error(`Invalid names: ${date}`);
		}
	}
};
