// WeekRow with Mini FillRing
function WeekRow({ week, index, onOpen, onContextMenu, onLongPressStart, onLongPressEnd }: any) {
  const lastUpdated = week.updated_at ? relativeTime(week.updated_at) : week.created_at ? relativeTime(week.created_at) : null;
  const statusColor = week.status === "published" ? "#34C759" : week.status === "draft" ? "#FF9500" : "#94A3B8";
  const miniRate = week.status === "published" ? 0.92 : week.status === "draft" ? 0.45 : 0;

  return (
    <motion.div layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8, scale: 0.98 }} onClick={onOpen} className="card flex items-center gap-4 px-4 py-3.5 cursor-pointer no-select active:shadow-card-press active:scale-[0.99] transition-all duration-100">
      <div className="relative flex items-center justify-center shrink-0">
        <FillRing rate={miniRate} size={42} strokeWidth={4.5} />
        <div className="absolute inset-0 flex items-center justify-center"><div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: statusColor }} /></div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-[15px] font-semibold text-gray-900 truncate">{week.label || `Week ending ${formatWeekEnding(week.week_ending)}`}</span>
          <StatusPill status={week.status} />
        </div>
        <div className="flex items-center gap-3 text-[12px] text-gray-400">
          <span>{formatWeekEnding(week.week_ending)}</span>
          {lastUpdated && <span className="flex items-center gap-1"><ClockIcon />{lastUpdated}</span>}
          {week.schedule_path ? <span className="flex items-center gap-1 text-emerald-600">📄 <span className="truncate max-w-[120px]">{week.schedule_path}</span></span> : <span className="text-gray-300">No schedule</span>}
        </div>
      </div>
      <span className="text-gray-300 shrink-0"><ChevronRightIcon /></span>
    </motion.div>
  );
}