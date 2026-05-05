-- ============================================================================
-- Migration 5: Backfill engine config from GLCR/Rules/*.json
-- Source files: Slot Difficulty.json, Slot Load Scores.json, Scorecard Weights.json,
-- Overlap Tasks.json, zone_geometry.json
-- Date: 2026-05-05
-- Generated programmatically from the source JSONs at the time of running.
-- ============================================================================
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Admin', 9, 'Supervisory duties, most complex role, high accountability');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone1', 7, 'High guest interaction, pit area, covers Zone 1+2 RR on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone2', 7, 'Pit area, lobby visibility, covers Zone 1+2 RR on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone3', 5, 'Moderate traffic, annex duties');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone4', 5, 'Moderate traffic');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone5', 7, 'High Limit table games, elevated guest expectations');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone6', 4, 'Lower traffic, often slow on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone7', 4, 'Lower traffic, often slow on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone8', 5, 'Pit 3, moderate traffic');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone9', 8, 'Smoking room complexity, social bar, high physical demand');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone10', 6, 'High Limit slots, outdoor area, pit 4');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Zone9SR', 8, 'Direct smoking room assignment, ventilation, physically demanding');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MRR1', 7, 'Zone 1+2 area, high traffic on weekends');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('WRR1', 7, 'Zone 1+2 area, high traffic on weekends');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MRR6', 5, 'Moderate traffic, also covers Zone 6 on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('WRR6', 5, 'Moderate traffic, also covers Zone 6 on weekdays');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MRR7', 5, 'Smoking room adjacent');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('WRR7', 5, 'Smoking room adjacent');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MRR8', 6, 'Multiple locations: Family RR, TDR, TMBR Locker Room');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('WRR8', 6, 'Multiple locations: Family RR, TDR, TMBR Locker Room');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MRR10', 5, 'CBK kitchen area');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('WRR10', 5, 'CBK kitchen area');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Trash1', 4, 'Lobby area sweep, moderate physical demand');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('Trash2', 4, 'Lobby area sweep, moderate physical demand');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MP1', 3, 'Float/multipurpose, lowest pressure slot');
INSERT INTO public.slot_difficulty (slot_id, difficulty, notes) VALUES ('MP2', 3, 'Float/multipurpose, lowest pressure slot');
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone1', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone2', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone3', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone4', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone5', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone6', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone7', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone8', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone9', 4);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone10', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Zone9SR', 5);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Z9SRBuddy', 4);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MRR1', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MRR6', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MRR7', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MRR8', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MRR10', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('WRR1', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('WRR6', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('WRR7', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('WRR8', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('WRR10', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Trash1', 4);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Trash2', 4);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Admin', 3);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MP1', 1);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('MP2', 1);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Support1', 1);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Support2', 1);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('Support3', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL1', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL2', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL3', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL4', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL5', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('PMOL6', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL1', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL2', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL3', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL4', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL5', 2);
INSERT INTO public.slot_load_scores (slot_id, load) VALUES ('AMOL6', 2);
INSERT INTO public.slot_load_config (id, sweeper_tag_bonus, training_role_bonus) VALUES (1, 2, '{"trainer": 1, "trainee": 1}'::jsonb);
INSERT INTO public.scorecard_config (id, weights, hard_preference_override_severity, fatigue_index_window_days, fatigue_threshold, pair_affinity_check_scope) VALUES (
  1,
  '{"skill_match": 1.0, "preference_fit": 1.5, "pair_affinity": 1.0, "within_repeat": 1.0, "cross_week_rotation": 0.5, "area_diversity": 0.7, "fatigue_index": 0.8, "soft_prefer_set": 0.6}'::jsonb,
  'warning',
  7,
  '{"fresh": 8, "moderate": 16, "stretched": 22, "burned": 28}'::jsonb,
  ARRAY['adjacent_zones', 'rr_pair_split', 'z9_sr_buddy', 'sweeper_co_route']::text[]
);
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL1', 'Vacuum, Bottles & Glass');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL2', 'Glass & Counters, Trash');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL3', 'Tables & Restroom, Bottles & Glass');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL4', 'Trash');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL5', 'Trash');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('PM', 'PMOL6', 'Trash');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL1', 'CBK / Shkodé');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL2', 'CBK / Shkodé Restrooms');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL3', 'Hotel Offices');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL4', 'Sandhill / Lobby Bar');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL5', '131 / Group Room / CBK Office');
INSERT INTO public.overlap_tasks (period, slot_id, task) VALUES ('AM', 'AMOL6', 'Trash');
INSERT INTO public.overlap_task_overrides (override_date, period, slot_id, task) VALUES ('2026-05-01', 'AM', 'AMOL4', 'Sandhill / Lobby Bar; 131 / Group Room / CBK Office');
INSERT INTO public.overlap_task_overrides (override_date, period, slot_id, task) VALUES ('2026-05-01', 'AM', 'AMOL5', 'Trash');
INSERT INTO public.zone_geometry (id, geometry) VALUES (1, '{"map_image": "Casino_Map/GLCR_FloorMap_DEC_2025_NoLogos.png", "map_dimensions": {"width": 8938, "height": 6478}, "coordinate_space": "png_pixels", "status": "COMPLETE \u2014 12 zones confirmed via iPad tap-placer + 7 restrooms + break groups", "restrooms_confirmed": {"RR1": {"x": 3563, "y": 2721, "label": "WRR1 / MRR1", "notes": "Below Rewards Center"}, "RR2": {"x": 2686, "y": 3712, "label": "WRR2 / MRR2", "notes": "West edge near Poker Room"}, "RR6": {"x": 4534, "y": 5709, "label": "WRR6 / MRR6", "notes": "South near Outdoor Patio"}, "RR7": {"x": 5930, "y": 5551, "label": "WZ7 / MRR7", "notes": "South near Smoking Slots"}, "RR8": {"x": 6227, "y": 3312, "label": "WZ8 / MRR8", "notes": "Between Cashier & High Limit Table"}, "RR10": {"x": 8326, "y": 4507, "label": "WZ10 / MRR10", "notes": "Far east Smoking Slots"}, "Lobby": {"x": 864, "y": 3493, "label": "Lobby Restroom", "notes": "Rotunda / Lobby Bar"}}, "zones_confirmed": {"Zone1": {"polygon": [[3046, 1715], [3946, 1715], [3946, 1958], [3655, 1976], [3673, 2507], [3455, 2489], [3455, 3211], [2776, 3316], [2654, 3081], [2689, 2959], [3081, 2776], [3081, 2576], [3029, 2576]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z1 \u2014 Parking garage corridor"}, "Zone2": {"polygon": [[3446, 3220], [3446, 3803], [3264, 4008], [3194, 4008], [3211, 4974], [3037, 4974], [3011, 4787], [2637, 4735], [2759, 4482], [2907, 4439], [2959, 4151], [2933, 3699], [2776, 3333]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z2 \u2014 Rotunda / Lobby corridor"}, "Zone3": {"polygon": [[3198, 4500], [4743, 4500], [5117, 4030], [4530, 4012], [4530, 3882], [3612, 3882], [3464, 3734], [3272, 4021], [3198, 4003]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z3 \u2014 Oasis perimeter / center floor"}, "Zone4": {"polygon": [[3203, 4496], [3220, 5044], [3616, 5044], [3616, 5296], [3716, 5296], [4021, 5466], [4734, 4496]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z4 \u2014 Poker Room / south corridor"}, "Zone5": {"polygon": [[4804, 4412], [5117, 3986], [5213, 3986], [5239, 3812], [5309, 3812], [5352, 3956], [5605, 3956], [5718, 3860], [5836, 3860], [5836, 3768], [5318, 3768], [5300, 3412], [5735, 3386], [5953, 3647], [6040, 3560], [6066, 4421], [5170, 4465]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z5 \u2014 High Limit Table / center"}, "Zone6": {"polygon": [[4813, 4430], [4029, 5474], [4421, 5692], [4543, 5527], [5004, 5509], [5187, 5553], [5170, 4447]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z6 \u2014 Table Games / south"}, "Zone7": {"polygon": [[5178, 4447], [6075, 4421], [6366, 4630], [6366, 5322], [5814, 5322], [5796, 5761], [5666, 5779], [5579, 5709], [5579, 5553], [5204, 5535]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z7 \u2014 Table Games / southeast"}, "Zone8": {"polygon": [[6040, 3446], [6066, 4421], [6379, 4630], [6836, 4630], [6836, 3420]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z8 \u2014 Center-east Table Games"}, "Zone9": {"polygon": [[6841, 3416], [7955, 3416], [7972, 3612], [8616, 3612], [8633, 3925], [7894, 3943], [7876, 3764], [7119, 3764], [7119, 3934], [6841, 3908]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z9 \u2014 NE row / cashier"}, "Zone10": {"polygon": [[6845, 3916], [6845, 4626], [6989, 4626], [6989, 4390], [8629, 4390], [8629, 3925], [7128, 3995], [7128, 3943]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z10 \u2014 Smoking Slots + High Limit Slots (inc. Z11 area on grave)"}, "Zone11": {"polygon": [[6993, 4390], [7589, 4390], [7589, 4617], [6993, 4617]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z11 \u2014 High Limit Slots sub-area (merged into Z10 on grave)"}, "Zone12": {"polygon": [[7728, 3203], [7728, 3394], [7963, 3412], [7963, 3616], [8498, 3616], [8498, 3120], [7916, 3120], [7916, 3168]], "source": "iPad tap-placer 2026-04-24, light cleanup applied", "label_grave": "Z12 \u2014 Z9 Smoking Room (grave shift)"}}, "zones_unconfirmed": {}, "oasis_oval": {"anchors": [[2079, 3592], [2056, 4314]], "note": "Oval rotunda \u2014 not a porter zone per Brian"}, "break_groups": {"1": {"times": ["12:45a", "2:30a", "4:45a"], "members": ["Zone1", "Zone4", "Zone7", "Zone10", "WZ6", "WZ10", "MZ8"]}, "2": {"times": ["1:00a", "3:00a", "5:00a"], "members": ["Zone2", "Zone5", "Zone8", "MZ1", "MZ6", "WZ7", "Trash1"]}, "3": {"times": ["1:15a", "3:30a", "5:15a"], "members": ["Zone3", "Zone6", "Zone9", "WZ1", "WZ8", "MZ7", "MZ10", "Trash2"]}}, "shift_overrides": {"grave": {"zone9sr_target": "Zone12", "_zone9sr_note": "On grave, the audit code ''Zone9SR'' (Z9 Smoking Room) is rendered on the Zone12 polygon \u2014 NE corner smoking slots.", "merged_zones": [{"operational": "Zone10", "includes": ["Zone10", "Zone11"], "note": "On grave shift Z10 and Z11 are worked as one zone; TM assigned to ''Zone10'' in the audit covers both polygon areas."}]}}}'::jsonb);
