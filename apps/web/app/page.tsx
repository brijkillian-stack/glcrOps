      {/* New Week Modal */}
      <AnimatePresence>
        {showNewWeekModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <motion.div initial={{ opacity: 0, scale: 0.96, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.96, y: 20 }} className="bg-white rounded-3xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
              <div className="px-6 py-5 border-b">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-[#007AFF]/10 flex items-center justify-center"><CalendarIcon /></div>
                  <div><div className="font-semibold text-lg">Create New Week</div><div className="text-sm text-gray-500">Start a fresh planning cycle</div></div>
                </div>
              </div>
              <div className="p-6">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Week Ending Date</label>
                <input type="date" value={newWeekDate} onChange={(e) => setNewWeekDate(e.target.value)} className="w-full h-11 px-4 rounded-2xl border border-gray-200 text-sm focus:outline-none focus:border-[#007AFF]" />
                <p className="text-[11px] text-gray-400 mt-1.5">This will create a draft week. You can upload the schedule later.</p>
              </div>
              <div className="px-6 py-4 border-t bg-gray-50 flex gap-3 justify-end">
                <button onClick={() => { setShowNewWeekModal(false); setNewWeekDate(""); }} className="h-10 px-5 rounded-2xl text-sm font-medium text-gray-600 hover:bg-gray-100">Cancel</button>
                <button onClick={handleCreateNewWeek} disabled={!newWeekDate || creatingWeek} className="h-10 px-6 rounded-2xl bg-[#007AFF] text-white text-sm font-semibold disabled:opacity-50">{creatingWeek ? "Creating…" : "Create Draft Week"}</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>