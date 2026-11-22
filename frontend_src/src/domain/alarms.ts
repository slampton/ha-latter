/**
 * Pure alarm-slot wire parser, serializer, and duration formatter (`L1` domain leaf).
 * Wire format: `HH:MM|<enabled 0|1>|<recurrence 0..3>;...` (3 fixed alarm slots).
 */

import { DEFAULT_ALARMS_SUMMARY } from "../constants.js";

export interface AlarmSlotView {
  time: string;
  enabled: boolean;
  recurrence: number;
}

export const DEFAULT_ALARM_SLOTS: readonly [AlarmSlotView, AlarmSlotView, AlarmSlotView] = [
  { time: "07:00", enabled: false, recurrence: 1 },
  { time: "08:30", enabled: false, recurrence: 2 },
  { time: "09:00", enabled: false, recurrence: 2 },
];

function parseSingleAlarmSlot(segRaw: string | undefined, fallback: AlarmSlotView): AlarmSlotView {
  const seg = (segRaw || "").trim();
  const m = /^(\d{1,2}):(\d{2})\|([01])\|([0-3])$/.exec(seg);
  if (!m) {
    return { ...fallback };
  }
  const hh = Number(m[1]);
  const mm = Number(m[2]);
  if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
    return { ...fallback };
  }
  return {
    time: `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
    enabled: m[3] === "1",
    recurrence: Number(m[4]),
  };
}

export function parseAlarmsSummary(raw: unknown): [AlarmSlotView, AlarmSlotView, AlarmSlotView] {
  const text = String(raw || DEFAULT_ALARMS_SUMMARY).trim();
  const parts = text.split(";");
  return [
    parseSingleAlarmSlot(parts[0], DEFAULT_ALARM_SLOTS[0]),
    parseSingleAlarmSlot(parts[1], DEFAULT_ALARM_SLOTS[1]),
    parseSingleAlarmSlot(parts[2], DEFAULT_ALARM_SLOTS[2]),
  ];
}

export function serializeAlarmsSummary(slots: ReadonlyArray<AlarmSlotView>): string {
  return slots
    .slice(0, 3)
    .map((s) => `${s.time}|${s.enabled ? 1 : 0}|${s.recurrence}`)
    .join(";");
}

export function formatClockDuration(rawSec: unknown): string {
  const sec = Math.max(0, Math.floor(Number(rawSec) || 0));
  const hh = Math.floor(sec / 3600);
  const mm = Math.floor((sec % 3600) / 60);
  const ss = sec % 60;
  if (hh > 0) {
    return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
  }
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
