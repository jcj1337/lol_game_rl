# Summoner's Rift map, movement, recall, death, tower and vision facts

## Reference patch

| item | value | source URL | status |
|---|---|---|---|
| Live patch | 26.22 (Riot naming); Data Dragon version 16.22.1 | https://www.leagueoflegends.com/en-us/news/tags/patch-notes/ and https://ddragon.leagueoflegends.com/api/versions.json | fetched |
| Patch notes published | 2026-11-03 19:00 UTC | https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-22-notes | fetched |
| Live date | 2026-11-04 (seen only in a search-result snippet; the Riot notes page does not state it) | none fetched | unverified |
| Systemic changes in 26.22 | none touching turrets, minions, vision, recall, homeguard, death timers, boots or map | same patch notes URL | fetched |
| Map data build | Community Dragon content 16.22.8348910 (both `latest` and `16.22` paths) | https://raw.communitydragon.org/16.22/content-metadata.json | fetched |
| Research date | 2026-11-11 | | |

Status legend:
- **fetched**: read on a page or file fetched this session.
- **fetched (derived)**: computed this session from fetched numbers (the arithmetic is mine, not a source statement).
- **unverified, from memory**: not confirmed this session.

Source abbreviations used in tables:
- WIKI = https://wiki.leagueoflegends.com/en-us/ (official League wiki; page name follows)
- RIOT 26.1 = https://www.leagueoflegends.com/en-us/news/game-updates/patch-26-1-notes/
- DD = https://ddragon.leagueoflegends.com/cdn/16.22.1/data/en_US/ (item.json, champion.json)
- CD-GEO = https://raw.communitydragon.org/16.22/game/data/maps/mapgeometry/map11/base_srx.materials.bin.json
- CD-MAP = https://raw.communitydragon.org/16.22/game/data/maps/shipping/map11/map11.bin.json

Fetch notes: the wiki blocks plain `curl` (bot challenge) but was readable through the fetch tool, which summarises with a small model, so wiki rows are model-extracted readings of the page, not byte-exact copies. Data Dragon and Community Dragon files were downloaded and parsed directly, so those numbers are exact.

---

## Coordinates (machine-copyable)

Coordinate system: Community Dragon stores each placed object as a 4x4 transform whose translation row is (x, height, z). The tables below give (x, z) as (x, y), which is the same plane Riot's Match-v5 timeline positions use. Blue (Order, team 100) base is bottom-left near (400, 450); red (Chaos, team 200) base is top-right near (14340, 14390). Values are rounded to 0.01. Team and lane come from the file's `Team` and `LaneDefinition` fields (lane 0 = bot, 1 = mid, 2 = top, inferred from positions; missing `Team` means blue).

All rows: source CD-GEO, parsed this session.

### Structures, spawns, shops, barracks

| name | x | y | source | status |
|---|---|---|---|---|
| blue_spawn_gate_locator (OrderSpawnGate) | 409 | 422 | CDragon base_srx | fetched |
| blue_spawn_point (__Spawn_T1, fountain) | 394 | 461 | CDragon base_srx | fetched |
| blue_fountain_laser_turret (record SRUAP_Turret_Order5) | 105 | 134 | CDragon base_srx | fetched |
| blue_shopkeeper | 40 | 1112 | CDragon base_srx | fetched |
| blue_bot_outer_turret | 10504 | 1029 | CDragon base_srx | fetched |
| blue_mid_outer_turret | 5846 | 6396 | CDragon base_srx | fetched |
| blue_top_outer_turret | 981 | 10441 | CDragon base_srx | fetched |
| blue_bot_inner_turret | 6919 | 1483 | CDragon base_srx | fetched |
| blue_mid_inner_turret | 5048 | 4812 | CDragon base_srx | fetched |
| blue_top_inner_turret | 1512 | 6699 | CDragon base_srx | fetched |
| blue_bot_inhibitor_turret | 4281 | 1253 | CDragon base_srx | fetched |
| blue_mid_inhibitor_turret | 3651 | 3696 | CDragon base_srx | fetched |
| blue_top_inhibitor_turret | 1169 | 4287 | CDragon base_srx | fetched |
| blue_bot_inhibitor | 3468.07 | 1230.95 | CDragon base_srx | fetched |
| blue_mid_inhibitor | 3210.62 | 3217.53 | CDragon base_srx | fetched |
| blue_top_inhibitor | 1172.7 | 3583.29 | CDragon base_srx | fetched |
| blue_nexus_turret_pos4 | 2177 | 1807 | CDragon base_srx | fetched |
| blue_nexus_turret_pos5 | 1748 | 2270 | CDragon base_srx | fetched |
| blue_nexus | 1550.67 | 1660.32 | CDragon base_srx | fetched |
| blue_bot_barracks (minion spawn) | 2034 | 1171 | CDragon base_srx | fetched |
| blue_mid_barracks (minion spawn) | 2008 | 2079 | CDragon base_srx | fetched |
| blue_top_barracks (minion spawn) | 1109 | 2091 | CDragon base_srx | fetched |
| red_spawn_gate_locator (ChaosSpawnGate) | 14298 | 14383 | CDragon base_srx | fetched |
| red_spawn_point (__Spawn_T2, fountain) | 14340 | 14391 | CDragon base_srx | fetched |
| red_fountain_laser_turret (record SRUAP_MageCrystal) | 14576 | 14693 | CDragon base_srx | fetched |
| red_shopkeeper | 13734.25 | 14552.57 | CDragon base_srx | fetched |
| red_bot_outer_turret | 13866 | 4505 | CDragon base_srx | fetched |
| red_mid_outer_turret | 8955 | 8510 | CDragon base_srx | fetched |
| red_top_outer_turret | 4318 | 13875 | CDragon base_srx | fetched |
| red_bot_inner_turret | 13327 | 8226 | CDragon base_srx | fetched |
| red_mid_inner_turret | 9767 | 10113 | CDragon base_srx | fetched |
| red_top_inner_turret | 7943 | 13411 | CDragon base_srx | fetched |
| red_bot_inhibitor_turret | 13624 | 10572 | CDragon base_srx | fetched |
| red_mid_inhibitor_turret | 11134 | 11207 | CDragon base_srx | fetched |
| red_top_inhibitor_turret | 10481 | 13650 | CDragon base_srx | fetched |
| red_bot_inhibitor | 13599.17 | 11319.92 | CDragon base_srx | fetched |
| red_mid_inhibitor | 11593.58 | 11669.57 | CDragon base_srx | fetched |
| red_top_inhibitor | 11275.23 | 13657.17 | CDragon base_srx | fetched |
| red_nexus_turret_pos4 | 12611 | 13084 | CDragon base_srx | fetched |
| red_nexus_turret_pos5 | 13052 | 12612 | CDragon base_srx | fetched |
| red_nexus | 13243 | 13235 | CDragon base_srx | fetched |
| red_bot_barracks (minion spawn) | 13719 | 12845 | CDragon base_srx | fetched |
| red_mid_barracks (minion spawn) | 12776 | 12784 | CDragon base_srx | fetched |
| red_top_barracks (minion spawn) | 12800 | 13745 | CDragon base_srx | fetched |
| map_center_locator (Locator_Map_Center) | 7457.75 | 7408.41 | CDragon base_srx | fetched |

### Jungle camps, river camps, pits

These are the camp anchor objects (`NeutralCampGeComponentDef`), one per camp, so they are exact file values but only approximate "where the monsters stand" (individual monster locators sit within about 250 units of the anchor).

| name | x | y | source | status |
|---|---|---|---|---|
| Baron_pit_camp [file CampName: Baron] | 5007 | 10471 | CDragon base_srx | fetched |
| Dragon_pit_camp [file CampName: Dragon] | 9837.67 | 4397.76 | CDragon base_srx | fetched |
| Rift_Herald_camp [file CampName: SRU_RiftHerald] | 4909.56 | 10487.32 | CDragon base_srx | fetched |
| Rift_Scuttler_bot_river (dragon side) [file CampName: Dragon Crab] | 10500 | 5170 | CDragon base_srx | fetched |
| Rift_Scuttler_top_river (baron side) [file CampName: Baron Crab] | 4400 | 9600 | CDragon base_srx | fetched |
| Voidgrub_camp [file CampName: Horde] | 4909.56 | 10487.32 | CDragon base_srx | fetched |
| blue_side_Blue_Sentinel [file CampName: Order Blue] | 3893.85 | 7869.83 | CDragon base_srx | fetched |
| blue_side_Gromp [file CampName: Order OwlBear] | 2177.79 | 8429.69 | CDragon base_srx | fetched |
| blue_side_Krugs [file CampName: Order Small Golems] | 8390 | 2675 | CDragon base_srx | fetched |
| blue_side_Murk_Wolves [file CampName: Order Wolves] | 3813.45 | 6466.75 | CDragon base_srx | fetched |
| blue_side_Raptors [file CampName: Order Wraiths] | 6969 | 5422 | CDragon base_srx | fetched |
| blue_side_Red_Brambleback [file CampName: Order Red] | 7765.24 | 4020.19 | CDragon base_srx | fetched |
| red_side_Blue_Sentinel [file CampName: Chaos Blue] | 11031.73 | 6990.84 | CDragon base_srx | fetched |
| red_side_Gromp [file CampName: Chaos OwlBear] | 12625.56 | 6434.19 | CDragon base_srx | fetched |
| red_side_Krugs [file CampName: Chaos Small Golems] | 6449 | 12199 | CDragon base_srx | fetched |
| red_side_Murk_Wolves [file CampName: Chaos Wolves] | 10979.8 | 8356.89 | CDragon base_srx | fetched |
| red_side_Raptors [file CampName: Chaos Wraiths] | 7861 | 9575 | CDragon base_srx | fetched |
| red_side_Red_Brambleback [file CampName: Chaos Red] | 7101.87 | 10900.55 | CDragon base_srx | fetched |

### Faelight sites (2026 vision feature)

| name | x | y | source | status |
|---|---|---|---|---|
| FaerieLightsGroup_OrderBaseBot | 4972.33 | 3094.7 | CDragon base_srx | fetched |
| FaerieLightsGroup_ChaosBaseBot | 11822.14 | 9899.98 | CDragon base_srx | fetched |
| FaerieLightsGroup_ChaosBaseTop | 9823.9 | 11830.26 | CDragon base_srx | fetched |
| FaerieLightsGroup_ChaosSplitPushBot | 12963 | 5903.25 | CDragon base_srx | fetched |
| FaerieLightsGroup_ChaosSplitPushTop | 5294.8 | 13021.98 | CDragon base_srx | fetched |
| FaerieLightsGroup_OrderBaseTop | 2900.73 | 5082.01 | CDragon base_srx | fetched |
| FaerieLightsGroup_OrderSplitPushBot | 9269.68 | 2148.42 | CDragon base_srx | fetched |
| FaerieLightsGroup_OrderSplitPushTop | 2336.77 | 9714.09 | CDragon base_srx | fetched |
| FaerieLightsGroup_RiverPixelBot | 11531.49 | 3853.63 | CDragon base_srx | fetched |
| FaerieLightsGroup_RiverPixelTop | 3345 | 11379 | CDragon base_srx | fetched |
| FaerieLightsGroup_RiverWallBot | 10058.54 | 6066.49 | CDragon base_srx | fetched |
| FaerieLightsGroup_RiverWallTop | 4914.43 | 8547.76 | CDragon base_srx | fetched |

### Lane paths: waypoints and cumulative length

`MinionPath_*` are the blue-side minion waypoint polylines (linked from the blue barracks; red barracks carry no separate path in the file, so red waves presumably walk the same polyline reversed: unverified). `*LaneHomeguardsPath` are the 2026 Homeguard endpoint tracks. Top lane turns between idx 5 and idx 10; bot lane turns between idx 5 and idx 10.

| path | idx | x | y | cumulative_length | source | status |
|---|---|---|---|---|---|---|
| MinionPath_Top | 0 | 1508 | 3597 | 0 | CDragon base_srx | fetched |
| MinionPath_Top | 1 | 1382 | 4910 | 1319.03 | CDragon base_srx | fetched |
| MinionPath_Top | 2 | 1170 | 6715 | 3136.44 | CDragon base_srx | fetched |
| MinionPath_Top | 3 | 1207 | 7787 | 4209.08 | CDragon base_srx | fetched |
| MinionPath_Top | 4 | 1229 | 9072 | 5494.27 | CDragon base_srx | fetched |
| MinionPath_Top | 5 | 1285 | 10423 | 6846.43 | CDragon base_srx | fetched |
| MinionPath_Top | 6 | 1508 | 11601 | 8045.35 | CDragon base_srx | fetched |
| MinionPath_Top | 7 | 1968 | 12459 | 9018.88 | CDragon base_srx | fetched |
| MinionPath_Top | 8 | 2720 | 13100 | 10007 | CDragon base_srx | fetched |
| MinionPath_Top | 9 | 3486 | 13473 | 10858.99 | CDragon base_srx | fetched |
| MinionPath_Top | 10 | 4359 | 13597 | 11740.75 | CDragon base_srx | fetched |
| MinionPath_Top | 11 | 5504 | 13608 | 12885.81 | CDragon base_srx | fetched |
| MinionPath_Top | 12 | 6668 | 13647 | 14050.46 | CDragon base_srx | fetched |
| MinionPath_Top | 13 | 8113 | 13665 | 15495.57 | CDragon base_srx | fetched |
| MinionPath_Top | 14 | 9889 | 13447 | 17284.9 | CDragon base_srx | fetched |
| MinionPath_Top | 15 | 11348 | 13344 | 18747.53 | CDragon base_srx | fetched |
| MinionPath_Mid | 0 | 2952 | 3474 | 0 | CDragon base_srx | fetched |
| MinionPath_Mid | 1 | 3856 | 4170 | 1140.89 | CDragon base_srx | fetched |
| MinionPath_Mid | 2 | 4874 | 5141 | 2547.72 | CDragon base_srx | fetched |
| MinionPath_Mid | 3 | 5375 | 5589 | 3219.81 | CDragon base_srx | fetched |
| MinionPath_Mid | 4 | 5823 | 5928 | 3781.61 | CDragon base_srx | fetched |
| MinionPath_Mid | 5 | 6270 | 6366 | 4407.44 | CDragon base_srx | fetched |
| MinionPath_Mid | 6 | 6764 | 6864 | 5108.89 | CDragon base_srx | fetched |
| MinionPath_Mid | 7 | 7408 | 7405 | 5949.97 | CDragon base_srx | fetched |
| MinionPath_Mid | 8 | 8079 | 8022 | 6861.53 | CDragon base_srx | fetched |
| MinionPath_Mid | 9 | 8618 | 8647 | 7686.84 | CDragon base_srx | fetched |
| MinionPath_Mid | 10 | 9149 | 9105 | 8388.07 | CDragon base_srx | fetched |
| MinionPath_Mid | 11 | 9625 | 9543 | 9034.93 | CDragon base_srx | fetched |
| MinionPath_Mid | 12 | 10193 | 10035 | 9786.38 | CDragon base_srx | fetched |
| MinionPath_Mid | 13 | 10822 | 10646 | 10663.29 | CDragon base_srx | fetched |
| MinionPath_Mid | 14 | 11808 | 11479 | 11954.06 | CDragon base_srx | fetched |
| MinionPath_Bot | 0 | 3471 | 1589 | 0 | CDragon base_srx | fetched |
| MinionPath_Bot | 1 | 4844 | 1440 | 1381.06 | CDragon base_srx | fetched |
| MinionPath_Bot | 2 | 6925 | 1163 | 3480.42 | CDragon base_srx | fetched |
| MinionPath_Bot | 3 | 7975 | 1230 | 4532.55 | CDragon base_srx | fetched |
| MinionPath_Bot | 4 | 8870 | 1212 | 5427.73 | CDragon base_srx | fetched |
| MinionPath_Bot | 5 | 10506 | 1301 | 7066.15 | CDragon base_srx | fetched |
| MinionPath_Bot | 6 | 11432 | 1472 | 8007.81 | CDragon base_srx | fetched |
| MinionPath_Bot | 7 | 12294 | 1913 | 8976.07 | CDragon base_srx | fetched |
| MinionPath_Bot | 8 | 13001 | 2628 | 9981.59 | CDragon base_srx | fetched |
| MinionPath_Bot | 9 | 13529 | 3694 | 11171.18 | CDragon base_srx | fetched |
| MinionPath_Bot | 10 | 13751 | 4790 | 12289.44 | CDragon base_srx | fetched |
| MinionPath_Bot | 11 | 13741 | 5811 | 13310.49 | CDragon base_srx | fetched |
| MinionPath_Bot | 12 | 13710 | 7177 | 14676.84 | CDragon base_srx | fetched |
| MinionPath_Bot | 13 | 13696 | 8608 | 16107.91 | CDragon base_srx | fetched |
| MinionPath_Bot | 14 | 13364 | 10040 | 17577.89 | CDragon base_srx | fetched |
| MinionPath_Bot | 15 | 13253 | 11334 | 18876.65 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 0 | 1162.37 | 3787.57 | 0 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 1 | 1294.41 | 9588.72 | 5802.65 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 2 | 1335.95 | 10904.38 | 7118.96 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 3 | 1395.37 | 11247.56 | 7467.26 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 4 | 1518.62 | 11753.01 | 7987.52 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 5 | 1737.18 | 12171.28 | 8459.44 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 6 | 2066.05 | 12625.77 | 9020.44 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 7 | 2522.17 | 13047.79 | 9641.85 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 8 | 3047.14 | 13310.12 | 10228.71 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 9 | 3641.06 | 13482.13 | 10847.04 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 10 | 4345.89 | 13602.75 | 11562.12 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 11 | 5178.81 | 13630.85 | 12395.51 | CDragon base_srx | fetched |
| TopLaneHomeguardsPath | 12 | 11042.56 | 13603.51 | 18259.33 | CDragon base_srx | fetched |
| MidLaneHomeguardsPath | 0 | 3196.11 | 3251.9 | 0 | CDragon base_srx | fetched |
| MidLaneHomeguardsPath | 1 | 11534.85 | 11585.64 | 11789.23 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 0 | 13631.17 | 11082.29 | 0 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 1 | 13583.66 | 5284.94 | 5797.55 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 2 | 13583.66 | 4179.32 | 6903.16 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 3 | 13499.21 | 3673.22 | 7416.27 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 4 | 13344.81 | 3202.2 | 7911.95 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 5 | 13115.55 | 2703.14 | 8461.15 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 6 | 12789.52 | 2289.53 | 8987.8 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 7 | 12429.23 | 1916.41 | 9506.48 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 8 | 11949.02 | 1562.3 | 10103.14 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 9 | 11451.64 | 1340.93 | 10647.55 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 10 | 10935.71 | 1256.67 | 11170.32 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 11 | 9827.44 | 1251.27 | 12278.61 | CDragon base_srx | fetched |
| BotLaneHomeguardsPath | 12 | 3500 | 1250 | 18606.04 | CDragon base_srx | fetched |

### Derived lane lengths

| lane | minion_path_length | blue_barracks_to_path_start | path_end_to_red_barracks | barracks_to_barracks | half (wave meeting distance) | spawn_to_spawn_via_lane | status |
|---|---|---|---|---|---|---|---|
| top | 18748 | 1558 | 1506 | 21812 | 10906 | 25262 | fetched (derived) |
| mid | 11954 | 1684 | 1625 | 15263 | 7632 | 19791 | fetched (derived) |
| bot | 18877 | 1497 | 1581 | 21954 | 10977 | 25408 | fetched (derived) |

### Derived straight-line checks

| quantity | value | status |
|---|---|---|
| straight-line blue fountain laser turret to red fountain laser turret | 20527 | fetched (derived); wiki says about 20500 |
| straight-line blue spawn point to red spawn point | 19711 | fetched (derived) |
| straight-line blue nexus to red nexus | 16452 | fetched (derived) |

### Derived arc distance of each lane structure along its lane

Arc distance is measured along spawn point -> barracks -> MinionPath -> enemy barracks -> enemy spawn point, projecting each structure onto that polyline. Walk time is distance / 335 with no Homeguard, no boots, no soft-cap effects.

| structure | lane | arc_distance_from_blue_spawn | arc_distance_from_red_spawn | lateral_offset_from_path | walk_seconds_from_own_spawn_at_335_MS_no_boost | status |
|---|---|---|---|---|---|---|
| blue_bot_outer_turret | bot | 10333 | 15075 | 271 | 30.8 | fetched (derived) |
| blue_mid_outer_turret | mid | 8095 | 11696 | 318 | 24.2 | fetched (derived) |
| blue_top_outer_turret | top | 10184 | 15077 | 305 | 30.4 | fetched (derived) |
| blue_bot_inner_turret | bot | 6716 | 18692 | 316 | 20.0 | fetched (derived) |
| blue_mid_inner_turret | mid | 6416 | 13375 | 358 | 19.2 | fetched (derived) |
| blue_top_inner_turret | top | 6419 | 18843 | 338 | 19.2 | fetched (derived) |
| blue_bot_inhibitor_turret | bot | 4125 | 21282 | 247 | 12.3 | fetched (derived) |
| blue_mid_inhibitor_turret | mid | 4659 | 15132 | 251 | 13.9 | fetched (derived) |
| blue_top_inhibitor_turret | top | 4057 | 21205 | 272 | 12.1 | fetched (derived) |
| blue_bot_inhibitor | bot | 3181 | 22227 | 343 | 9.5 | fetched (derived) |
| blue_mid_inhibitor | mid | 3902 | 15889 | 358 | 11.6 | fetched (derived) |
| blue_top_inhibitor | top | 3239 | 22023 | 321 | 9.7 | fetched (derived) |
| red_bot_outer_turret | bot | 15317 | 10091 | 169 | 30.1 | fetched (derived) |
| red_mid_outer_turret | mid | 11822 | 7969 | 324 | 23.8 | fetched (derived) |
| red_top_outer_turret | top | 15077 | 10185 | 281 | 30.4 | fetched (derived) |
| red_bot_inner_turret | bot | 19013 | 6394 | 373 | 19.1 | fetched (derived) |
| red_mid_inner_turret | mid | 13485 | 6306 | 338 | 18.8 | fetched (derived) |
| red_top_inner_turret | top | 18660 | 6601 | 252 | 19.7 | fetched (derived) |
| red_bot_inhibitor_turret | bot | 21369 | 4038 | 305 | 12.1 | fetched (derived) |
| red_mid_inhibitor_turret | mid | 15233 | 4558 | 227 | 13.6 | fetched (derived) |
| red_top_inhibitor_turret | top | 21199 | 4063 | 244 | 12.1 | fetched (derived) |
| red_bot_inhibitor | bot | 22249 | 3159 | 335 | 9.4 | fetched (derived) |
| red_mid_inhibitor | mid | 15883 | 3908 | 284 | 11.7 | fetched (derived) |
| red_top_inhibitor | top | 21991 | 3271 | 307 | 9.8 | fetched (derived) |

---

## A. Map geometry

| id | fact | value | source URL | status |
|---|---|---|---|---|
| A1a | Map bounds used for Match timeline positions (map 11) | min (-120, -120), max (14870, 14980) game units | https://hextechdocs.dev/map-data/ (community mirror of old Riot docs; Riot's own https://developer.riotgames.com/docs/lol was fetched and no longer contains the bounds) | fetched |
| A1b | Practical playable square | about 0 to 14,800 on both axes; blue spawn (394, 461), red spawn (14340, 14391) | CD-GEO | fetched |
| A1c | Distance between the two Nexus Obelisks | "about 20500 units" on the wiki; 20527 computed from CD-GEO fountain laser turret coordinates | WIKI Summoner's_Rift; CD-GEO | fetched |
| A2 | Fountains, nexuses, all 22 turrets, 6 inhibitors | see "Structures" table | CD-GEO | fetched |
| A3 | Six jungle camps per side, both scuttlers, dragon and baron pits | see "Jungle camps" table | CD-GEO | fetched |
| A4a | Lane path lengths | no source states them. Blue minion polyline length: top 18,748, mid 11,954, bot 18,877. Barracks to barracks: top 21,812, mid 15,263, bot 21,954. Spawn to spawn via lane: top 25,262, mid 19,791, bot 25,408 | CD-GEO | fetched (derived) |
| A4b | Top lane corner | polyline bends through (1285, 10423) -> (1508, 11601) -> (1968, 12459) -> (2720, 13100) -> (3486, 13473) -> (4359, 13597) | CD-GEO | fetched |
| A4c | Bot lane corner | polyline bends through (10506, 1301) -> (11432, 1472) -> (12294, 1913) -> (13001, 2628) -> (13529, 3694) -> (13751, 4790) | CD-GEO | fetched |
| A4d | Mid lane | near-straight diagonal from (2952, 3474) to (11808, 11479); map centre locator at (7457.75, 7408.41) | CD-GEO | fetched |
| A5a | First minion wave spawn time | 0:30 (was 1:05 before patch 26.1) | RIOT 26.1; WIKI Minion; CD-MAP BarracksConfig `InitialSpawnTimeSecs` 30 | fetched |
| A5b | Wave interval | 30 s; 25 s from 14:00; 20 s from 30:00. Minions within a wave spawn about 0.8 s apart (wiki 0.792, file 0.8) | WIKI Minion; CD-MAP | fetched |
| A5c | First wave meeting time, mid | about 0:52 (7,632 units each at 350 MS = 21.8 s after 0:30) | CD-GEO + WIKI Minion | fetched (derived) |
| A5d | First wave meeting time, top and bot | about 1:01 (10,906 and 10,977 units at 350 MS = 31.2 and 31.4 s after 0:30). First wave gets no side-lane speed boost | CD-GEO + WIKI Minion | fetched (derived) |
| A5e | Sanity check of A5c and A5d | same geometry with the pre-2026 values (spawn 1:05, 325 MS) gives 1:28 mid and 1:39 side, which matches the commonly quoted old meeting times | old meeting times are from memory | unverified, from memory |
| A5f | Fountain to own outer turret walking distance | top 10,184, mid 8,095, bot 10,333 units from blue spawn; red 10,185 / 7,969 / 10,091. At 335 MS unboosted: about 30 s side lanes, 24 s mid | CD-GEO | fetched (derived) |
| A5g | First wave is ghosted (no unit collision) | 28 s top and bot, 18 s mid | WIKI Minion | fetched |
| A5h | Jungle camp first spawns (calibration only) | Blue, Red, Wolves, Raptors 0:55; Gromp, Krugs 1:07; Rift Scuttler 2:55; Baron 20:00 | RIOT 26.1; WIKI V26.01 | fetched |
| A5i | Minion experience and gold share radii | ExpRadius 1500, goldRadius 1250 | CD-MAP BarracksConfig {147211fb} | fetched |

## B. Movement

| id | fact | value | source URL | status |
|---|---|---|---|---|
| B6a | Champion base movement speed range | 325 to 355 across 173 champions (counts: 325 x19, 330 x38, 335 x42, 340 x37, 345 x28, 350 x7, 355 x1 Master Yi); single outlier Rell at 315 | DD champion.json | fetched |
| B6b | Boots (tier 1) | +25 MS, 300 gold | DD item.json; WIKI Boots | fetched |
| B6c | Tier 2 boots on Summoner's Rift | +45 MS: Berserker's Greaves (1100 g), Sorcerer's Shoes (1100), Plated Steelcaps (1200), Mercury's Treads (1250), Ionian Boots of Lucidity (900), Gluttonous Greaves (1100). +55 MS: Boots of Swiftness (1000 g, slows 25% weaker) | DD item.json | fetched |
| B6d | Tier 3 boots | Swiftmarch +65 MS; Crimson Lucidity, Chainlaced Crushers, Armored Advance, Spellslinger's Shoes, Immortal Path +45 MS. Granted by the mid-lane role quest (upgrades tier 2 to tier 3) | DD item.json; WIKI V26.01 | fetched |
| B6e | Whether tier 3 boots can be obtained any other way in 26.22 | not confirmed | | unverified, from memory |
| B6f | Movement speed formula and soft caps | (base + flat) x (1 + sum of additive %) x product of multiplicative, x (1 - highest slow). Raw 415 to 490: final = raw x 0.8 + 83. Raw above 490: final = raw x 0.5 + 230. Raw below 220: final = 110 + raw x 0.5 | WIKI Movement_speed | fetched |
| B7a | Homeguard availability | from 0:20; refreshes while inside the Homeguard endpoints; no fixed duration since 26.1 | WIKI Homeguard | fetched |
| B7b | Homeguard speed before 14:00 | +80% MS, decaying to +40% over 4 s after leaving the fountain | WIKI Homeguard; RIOT 26.1 | fetched |
| B7c | Homeguard speed after 14:00 (Riot notes: or after a turret falls in the lane) | +150% MS, decaying to +65% over 4 s | WIKI Homeguard; RIOT 26.1 | fetched |
| B7d | Homeguard endpoint | starts 500 units behind the lane's outer turret; after 14:00 or once an outer turret falls it tracks to about 2000 units before the furthest minion. Losing side cap: 500 units before the outermost living structure. Winning side cap: 2000 units before the inhibitor turret | WIKI Homeguard; https://www.riftpatchnotes.com/lol/system/map | fetched |
| B7e | Homeguard removal | entering combat or the jungle removes it and blocks regaining it for 8 s (cleared by completing a Recall); Teleport completion removes it | WIKI Homeguard | fetched |
| B7f | Respawn Homeguard (Deathguard) | +75% MS on respawn before 14:00, no fixed duration since 26.1 | WIKI Homeguard | fetched |
| B7g | Homestart | granted at game start, refreshes in spawn for the first 55 s; "massive decaying" speed, number not given | WIKI Homeguard; WIKI Fountain | fetched |
| B7h | Jungler out-of-combat speed | +4% in jungle and river, +8% after the jungle role quest | WIKI V26.01 | fetched |
| B8a | Lane minion base movement speed | 350 (was 325 before 26.1) | RIOT 26.1; WIKI Minion | fetched |
| B8b | Minion speed scaling | +25 four times, giving 350 / 375 / 400 / 425 / 450. Wiki display says steps at 11:00, 16:00, 21:00, 26:00; the data file says first step after 600 s then every 300 s, max 4 times | WIKI Minion; CD-MAP BarracksConfig {147211fb} | fetched (two sources disagree on exact step times, see conflicts) |
| B8c | Side-lane catch-up speed | after the first wave and until 14:00, top and bot minions get bonus MS on spawn: 111 on the second wave, minus 4.5 per later wave; removed in four stages (7, 7, 7, 4 s), each stage removing 15 | WIKI Minion | fetched |

## C. Recall and base

| id | fact | value | source URL | status |
|---|---|---|---|---|
| C9a | Recall channel | 8 s channel after a 0.5 s cast time; blinks to own fountain; no cooldown | WIKI Recall | fetched |
| C9b | Empowered Recall | 4 s channel after a 0.5 s cast time; granted by Hand of Baron or Glimpse of the Void buff | WIKI Recall | fetched |
| C9c | Mid-lane role quest reward | Empowered Recall on a 5 minute cooldown; champion takedowns cut the cooldown by 60 s | RIOT 26.1; WIKI V26.01 | fetched |
| C9d | Interrupts | movement, taking damage, death, immobilising or grounding or cast-inhibiting crowd control, Flash, Teleport, dashes, most item actives. Damage in the final 0.1 s, damage reduced to 0, and damage absorbed by shields or invulnerability do not interrupt | WIKI Recall | fetched |
| C10a | Fountain healing | 2% of max health every 0.25 s (8% per second) | WIKI Fountain; CD-MAP constants `sp_HealthRegenPercent` 0.02, `sp_RegenTickInterval` 0.25 | fetched |
| C10b | Fountain mana | 2.5% of max mana every 0.25 s (10% per second) | WIKI Fountain; CD-MAP `sp_ManaRegenPercent` 0.025 | fetched |
| C10c | Extra regen while Homeguard is active in the fountain | 8% of missing health and 8% of missing mana every 0.5 s | WIKI Fountain; WIKI Homeguard | fetched |
| C10d | Fountain regen radius | 1100 units (`sp_RegenRadius`); assumed to apply to classic 5v5 since it sits in the base constants group | CD-MAP | fetched (applicability inferred) |
| C10e | Full heal time from empty | about 12.5 s for health at 8% per second, about 10 s for mana, faster with C10c | C10a, C10b | fetched (derived) |
| C11a | Where items can be bought | "Items can only be purchased and sold while near the stall" (the shopkeeper at the fountain). Shop UI opens anywhere, and out of range you can only queue | WIKI Shop | fetched |
| C11b | Shop range in units | not stated on the wiki. The shop object in the map file carries hashed fields with values 1000 and 400 whose meaning I could not confirm | CD-GEO SRS_Shop | unverified, from memory |
| C11c | Buying while dead | allowed (dead champions can shop) | not on any fetched page | unverified, from memory |

## D. Death and respawn

| id | fact | value | source URL | status |
|---|---|---|---|---|
| D12a | Base respawn wait (BRW) by level 1 to 18, seconds | 10, 10, 12, 12, 14, 16, 20, 25, 28, 32.5, 35, 37.5, 40, 42.5, 45, 47.5, 50, 52.5 | WIKI Death; identical array in CD-MAP DeathTimes {9de5b46c} `mTimeDeadPerLevel` | fetched |
| D12b | Time increase factor (TIF), 0:00 to 14:59 | none; death time = BRW | WIKI Death | fetched |
| D12c | TIF, 15:00 to 29:59 | ceil(2 x (minutes - 15)) x 0.425%, range 0.425% to 12.75% | WIKI Death; CD-MAP scaling point 900 s, 0.00425 per 30 s | fetched |
| D12d | TIF, 30:00 to 44:59 | 12.75% + ceil(2 x (minutes - 30)) x 0.30%, range 13.05% to 21.75% | WIKI Death; CD-MAP scaling point 1800 s, 0.003 | fetched |
| D12e | TIF, 45:00 to 54:59 | 21.75% + ceil(2 x (minutes - 45)) x 1.45%, range 23.2% to 50.75%, capped at 50% | WIKI Death; CD-MAP scaling point 2700 s, 0.0145, `mScalingPercentCap` 1.5 | fetched |
| D12f | Total | death time = BRW + BRW x TIF; TIF steps every 30 s; displayed timer rounds up; maximum 78.75 s (level 18, 55:00 onward) | WIKI Death | fetched |
| D12g | Levels 19 and 20 (top-lane quest raises the cap to 20) | not stated anywhere I fetched; the data array has only 18 entries | | unverified, from memory |
| D12h | Which CD-MAP DeathTimes record is classic 5v5 | inferred by matching the wiki table; the file holds 8 records for different modes | CD-MAP | fetched (applicability inferred) |

## E. Lane towers

| id | fact | value | source URL | status |
|---|---|---|---|---|
| E13a | Health | outer 9000, inner 5000, inhibitor turret 4750, nexus turret 3500 | WIKI Turret; RIOT 26.1 | fetched |
| E13b | Armor and magic resist | 60 and 60 on every tier. Outer turrets lose 15 of each per minute from 11:00 to 15:00, capped at -60 (so 0 at 15:00) | WIKI Turret; RIOT 26.1 | fetched |
| E13c | Attack damage, outer | 182 at 0:00, +12 at 0:30 and every minute after, capped at 350 at 13:30 | WIKI Turret (raw wikitext) | fetched |
| E13d | Attack damage, inner and inhibitor turret | 187 at 0:00, +16 at 3:00 and every minute after, capped at 427 at 17:00 | WIKI Turret (raw wikitext) | fetched |
| E13e | Attack damage, nexus turret | 165 at 0:00, +16 at 3:00 and every minute after, capped at 405 at 17:00 | WIKI Turret (raw wikitext) | fetched |
| E13f | Attack range, attack speed, projectile speed | 750 range, 0.833 attacks per second, projectile speed 1200, gameplay radius 88.4 | WIKI Turret | fetched |
| E13g | Ramping damage against champions ("Warming Up", listed under the turret item Ohmwrecker) | +50% damage per consecutive hit on a champion, up to +150%; resets 5 s after the last champion hit; does not reset when switching targets; turret shots have 30% armor penetration | WIKI Turret | fetched |
| E13h | Damage taken from melee champions | turrets take 20% more damage from melee champions (since 26.1) | WIKI Turret; RIOT 26.1 | fetched |
| E13i | Crystalline Overgrowth (new in 26.1) | lane turrets crystallise after 90 s; next enemy champion attack consumes it for bonus true damage of 2% to 3.3% of turret max health (attacking team average level 1) up to 8.8% to 18.9% (level 18); sits at minimum 60 s, ramps linearly over 240 s; not consumed while backdoor protection is active | WIKI Turret; RIOT 26.1 | fetched |
| E13j | Regeneration | inhibitor turrets 3 HP/s up to the next of 30 / 75 / 100%; nexus turrets 6 HP/s up to the next of 40 / 70 / 100% | WIKI Turret | fetched |
| E13k | Nexus turret respawn | 3 minutes after destruction, at 40% max health | WIKI Turret | fetched |
| E14a | Plates | 5 per turret on outer, inner and inhibitor turrets (inner and inhibitor plates are new in 26.1) | WIKI Turret; RIOT 26.1 | fetched |
| E14b | Plate break thresholds | at 10 / 25 / 45 / 70 / 100% missing health (was 20 / 40 / 60 / 80 / 100%) | RIOT 26.1; WIKI V26.01 | fetched |
| E14c | Health per plate | 10%, 15%, 20%, 25%, 30% of max. Outer: 900 / 1350 / 1800 / 2250 / 2700. Inner: 500 / 750 / 1000 / 1250 / 1500. Inhibitor turret: 475 / 712.5 / 950 / 1187.5 / 1425 | from E13a and E14b | fetched (derived) |
| E14d | Gold per plate | 120 local gold (was 125). Outer plates lose 10 gold per minute from 11:00, capped at -40, so 80 from 15:00 | WIKI Turret; RIOT 26.1 | fetched |
| E14e | When plates fall | never. "Turret plating is no longer removed at 14:00" (26.1) | WIKI Turret; RIOT 26.1 | fetched |
| E14f | Bulwark on plate break | each broken plate gives the turret 30 to 50 bonus armor and MR (by enemy champions within 850) for 20 s, stacking up to 4; durations overlap | WIKI Turret (30 to 50 since 26.3) | fetched |
| E14g | Early Fortification | removed. Top and mid outer turrets lost it in 25.5; no Summoner's Rift turret lists it now | WIKI Turret | fetched |
| E14h | Lane Swap Detector | added to top and mid outer turrets in 25.5, removed in 26.1 | WIKI Turret | fetched |
| E15a | Global gold per turret (to every teammate) | outer 50, inner 25, inhibitor turret 25, nexus turret 50 | WIKI Turret | fetched |
| E15b | Local gold for the kill itself | 0 on every tier since 26.1 (outer was 250, inner 425/675, inhibitor turret 375); local gold now comes only from plates: up to 600 per turret, 400 minimum on a decayed outer | WIKI Turret; RIOT 26.1 | fetched |
| E15c | First turret bonus | 300 gold (wiki: bonus on first takedown; Riot notes: shared by nearby players) | WIKI Turret; RIOT 26.1 | fetched |
| E15d | Local gold sharing rule | split among living allied champions within 1200 units; killer and assisters (last 10 s) get a share regardless of range | WIKI Turret | fetched |
| E16a | Backdoor protection (Reinforced Armor) | incoming damage, including true damage, reduced by 80% when no enemy minions or summoned Rift Herald are nearby; turns off immediately when they arrive, back on 3 s after they leave. Listed on all turret tiers. The "nearby" radius is not given | WIKI Turret | fetched |
| E16b | Structure gating | a turret is invulnerable until the turret in front of it in the lane is destroyed; nexus turrets only become vulnerable once an inhibitor is down | WIKI Turret | fetched |
| E16c | Target priority (highest first) | most pets; siege or super minion; Mist Walkers; melee minion; caster minion; small summons; champion | WIKI Turret | fetched |
| E16d | Switch to a champion | if not already attacking a champion, the turret switches to an enemy champion that damages an allied champion within 1400 units, even if the damage is blocked or 0 | WIKI Turret | fetched |
| E17 | Turret sight radius | 1350; true sight (Warden's Eye) 1100 | WIKI Turret; WIKI Sight; WIKI V26.01 | fetched |

## F. Vision

| id | fact | value | source URL | status |
|---|---|---|---|---|
| F18a | Champion sight radius | 1350 (also pets, super minions, turrets), measured centre to centre | WIKI Sight | fetched |
| F18b | Minion sight radius | 1200 for melee, caster and siege minions; 1350 for super minions | WIKI Sight | fetched |
| F18c | Ward sight radius | 900 for Stealth Wards, Totem Wards and Control Wards; 500 for Farsight Wards | WIKI Sight | fetched |
| F18d | Attack-from-fog reveal | attacker is revealed in a 300 radius for 2 s | WIKI Sight; WIKI Brush | fetched |
| F19a | Stealth Ward trinket charges | 2 charges, 2 s between uses | WIKI Stealth_Ward; DD item 3340 | fetched |
| F19b | Stealth Ward trinket recharge | 210 to 90 s, scaling with average champion level (26.1 set 170 to 90; 26.3 set 210 to 90; before 2026 it was 210 to 120) | WIKI Stealth_Ward; DD item 3340 | fetched |
| F19c | Stealth Ward duration | 90 to 120 s by average champion level; 3 health; 625 placement range; 10 gold to the killer | WIKI Stealth_Ward | fetched |
| F19d | Maximum Stealth Wards per player | 3 on the map (shared between Stealth and Totem wards); placing a fourth removes the oldest (the removal behaviour is from memory) | WIKI Stealth_Ward | fetched |
| F19e | Control Ward | 75 gold (40 after the support quest), hold up to 2, 1 on the map per player, 4 health, 900 sight, visible to enemies; reveals and disables enemy wards, reveals traps and camouflaged champions | WIKI Control_Ward; DD item 2055 | fetched |
| F19f | Control Ward lifetime | lasts until destroyed or replaced | not stated on the fetched page | unverified, from memory |
| F19g | Oracle Lens | 2 charges, recharge 160 to 100 s by average level, sweeps for 8 s (was 6 s before 26.1) in a 600 to 750 radius by level; reveals and disables stealthed wards, reveals traps, shows hidden units as silhouettes | WIKI Oracle_Lens; DD item 3364 | fetched |
| F19h | Farsight Alteration | cooldown 198 to 99 s; places a visible 500-radius ward at long range | DD item 3363; WIKI Sight | fetched |
| F19i | Faelights (new in 26.1) | a ward placed on a Faelight site gets +25% vision radius and reveals a bonus region for 45 s; 8 sites at game start, 4 more after the Elemental Rift transformation | WIKI V26.01; RIOT 26.1 | fetched |
| F20a | Brush, concealment | units inside brush are hidden from enemies outside it unless the enemy team has sight inside (a unit or ward inside that brush, or a vision ability); units inside see out normally | WIKI Brush; WIKI Sight | fetched |
| F20b | Brush, counts | 39 brush patches on Summoner's Rift; attacking or casting a targeted ability from brush reveals a 300 radius for 2 s | WIKI Brush | fetched |
| F21 | Rift Scuttler Speed Shrine | vision radius 525 for 90 s; grants 30% bonus MS for 1.5 s to out-of-combat champions crossing it; first spawn 2:55, respawn 2:30 | WIKI Rift_Scuttler | fetched |

---

## Rules changed in the last two seasons that older knowledge gets wrong

| id | change | patch | status |
|---|---|---|---|
| X1 | Whole game clock moved 35 s earlier: minions spawn 0:30 (was 1:05), first camps 0:55 (was 1:30), Gromp and Krugs 1:07, Scuttler 2:55 (was 3:30), passive gold from 1:05 | 26.1 | fetched |
| X2 | Turret plates never fall off; inner and inhibitor turrets also have 5 plates; plates are unequal (10 / 15 / 20 / 25 / 30% of health); 120 gold each | 26.1 | fetched |
| X3 | Turret kill gives no local gold; only 25 to 50 global gold plus the plates. First-turret bonus is 300 again (it was removed in 25.S1.1) | 26.1 | fetched |
| X4 | Outer turrets have 9000 HP and 60 resists (was 5000 and 40), then decay to 0 resists between 11:00 and 15:00 | 26.1 | fetched |
| X5 | Turrets take +20% damage from melee champions; Crystalline Overgrowth gives periodic bonus true damage to turrets | 26.1 | fetched |
| X6 | Early Fortification on outer turrets is gone (25.5); the Lane Swap Detector that replaced it is also gone (26.1) | 25.5, 26.1 | fetched |
| X7 | Nexus turrets respawn 3 minutes after dying (since 25.S1.1), now at 40% health | 25.S1.1, 26.1 | fetched |
| X8 | Homeguard is available from 0:20, has no duration, runs to a lane endpoint (500 units behind the outer turret, later 2000 units behind the wave), and is lost on entering combat or the jungle | 25.S1.1, 26.1 | fetched |
| X9 | Minion base speed 350 (was 325); waves every 25 s from 14:00 and every 20 s from 30:00; first cannon wave is wave 3 (1:30) | 26.1 | fetched |
| X10 | Role quests: top raises level cap to 20 and grants Unleashed Teleport; mid grants tier 3 boots and a 4 s Recall every 5 minutes; support gets 40-gold Control Wards and an extra ward slot | 26.1 | fetched |
| X11 | Stealth Ward trinket recharge is 210 to 90 s (26.1 made it 170 to 90, 26.3 made it 210 to 90; it was 210 to 120 before); Oracle Lens has 2 charges and lasts 8 s (was 6 s) | 26.1, 26.3 | fetched |
| X12 | Faelight ward sites give boosted ward vision | 26.1 | fetched |
| X13 | Baron first spawns at 20:00 (was 25:00) | 26.1 | fetched |
| X14 | Fountain heals 8% max HP per second and 10% max mana per second (was 10.4% and 12.4%) | 25.7 | fetched |
| X15 | Backdoor protection is 80% damage reduction and also reduces true damage (was 66.67%) | 14.1 | fetched |
| X16 | Death timer table is not the old linear "level x 2.5 + 7.5": levels 1 to 9 are 10, 10, 12, 12, 14, 16, 20, 25, 28; time scaling only starts at 15:00 | patch not identified | fetched for the table; the comparison to the old formula is from memory |
| X17 | All standard tier 2 boots give +45 MS and Boots of Swiftness +55; Mobility Boots are no longer purchasable | patch not identified | fetched for current values; the "older" values are from memory |

---

## Conflicts and gaps

1. **Minion speed step times.** The wiki's displayed schedule is 350 to 450 with steps at 11:00, 16:00, 21:00, 26:00, but the same page's formula text says "+25 for every 5 minutes after 6:00", and the data file says first step 600 s after some reference time, then every 300 s. Since first spawn moved to 0:30, the steps may now land at 10:30 or 10:00 rather than 11:00. Not resolved.
2. **Wave composition after 30:00.** The wiki Minion page says one fewer caster; the wiki V26.01 page says one fewer melee and one fewer caster. Not resolved.
3. **Nexus turret plates.** The Riot 26.1 notes extract listed plate thresholds under nexus turrets; the wiki Turret page lists plating only on outer, inner and inhibitor turrets. Treat nexus turrets as plate-less unless confirmed.
4. **Outer turret previous resists.** Riot 26.1 notes extract said base resists went 15 to 60; the wiki says 40 to 60. Only the current value (60) matters and both agree on it.
5. **Homeguard after-14:00 trigger.** The wiki ties the +150% tier to 14:00; the Riot notes extract says 14:00 or after any turret falls in that lane. The endpoint change is tied to "14:00 or an outer turret falls" in both.
6. **Backdoor protection radius** ("nearby" minions) is not given on the wiki page.
7. **Death timers for levels 19 and 20** are not documented on the fetched pages and the data array stops at 18.
8. **Shop purchase radius** is not documented; the map file has unlabelled values 1000 and 400.
9. **Map bounds** come from a community documentation mirror; Riot's current developer docs page no longer lists them.
10. **Red-side minion path.** Only blue barracks link to a path object; I assumed red waves walk the same polyline reversed. Lane lengths and meeting times depend on this.
11. **Wave meeting times and walk times are computed, not sourced.** No fetched page states them. They ignore unit collision, minion spawn stagger (0.8 s per minion), turning, and Homeguard.
12. **Turret damage ramp** is described on the wiki under the turret item Ohmwrecker; I did not confirm which turret tiers carry that item.
13. **Wiki extraction caveat.** Wiki pages were read through a summarising fetch tool (pages of 140k to 330k characters, read in 100k windows). Numbers were cross-checked against Riot's 26.1 notes, Data Dragon or Community Dragon where possible (turret HP, plates, minion spawn, fountain regen, death timer table, ward trinket numbers, boots). Rows with a single wiki source and no cross-check: recall cast time 0.5 s, turret AD schedule, Bulwark numbers, target-switch range 1400, sight radii, Scuttler shrine radius.
14. **Live date of 26.22** (2026-11-04) was only seen in a search snippet.
15. **Not fetched:** Bayes Esports tower coordinate page (DNS failure), so the turret coordinates have no second independent source this session. They do match the building positions I remember from Match-v5 timelines (from memory).
