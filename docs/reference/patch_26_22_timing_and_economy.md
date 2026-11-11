# LoL Summoner's Rift 5v5: timing and economy reference

## Reference patch

- **Reference patch: 26.22** (wiki name V26.22). Release date (US) **2026-11-04**; official notes published 2026-11-03T19:00Z. Research date 2026-11-11.
  - https://wiki.leagueoflegends.com/en-us/V26.22 (fetched: "Release Date (US) November 4th, 2026"; next entry is PBE 26.23, no date)
  - https://wiki.leagueoflegends.com/en-us/Patch/2026_Annual_Cycle (fetched: V26.22 = November 4, 2026; V26.21 = October 21, 2026)
  - https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-22-notes/ (fetched: no minion, jungle, gold, XP, support-item or jungle-item changes in 26.22)
- One search result claimed a Nov 21 live date for 26.22; the wiki and Riot's news index both support Nov 4. Treated as live.
- Wiki pages carry no "reflects patch X" stamp. Each page's newest patch-history entry is noted where relevant. The Minion page carries an "outdated" banner on its Minion interactions section.

### How to read the status column

- **fetched** = read on a page fetched this session. All fetches went through a summarizing fetch tool that paraphrases and limits verbatim quotes, so a value is "as reported from the page", not a byte-exact copy. Rows marked **fetched x2** were confirmed on two independent pages (usually wiki plus Riot patch notes).
- **fetched (derived)** = arithmetic on fetched values; the page did not state the total itself.
- **unverified, from memory** = not confirmed on any fetched page.
- Direct `curl` of the wiki is blocked by a bot challenge (HTTP 403); Fandom returned HTTP 402 on every attempt, so the Fandom fallback was unavailable.

Short source keys used below:

- W-Minion = https://wiki.leagueoflegends.com/en-us/Minion_(League_of_Legends)
- W-Melee = https://wiki.leagueoflegends.com/en-us/Melee_minion
- W-Caster = https://wiki.leagueoflegends.com/en-us/Caster_minion
- W-Siege = https://wiki.leagueoflegends.com/en-us/Siege_minion
- W-Super = https://wiki.leagueoflegends.com/en-us/Super_minion
- W-XP = https://wiki.leagueoflegends.com/en-us/Experience_(champion)
- W-Gold = https://wiki.leagueoflegends.com/en-us/Gold
- W-Bounty = https://wiki.leagueoflegends.com/en-us/Champion_gold_bounties
- W-Kill = https://wiki.leagueoflegends.com/en-us/Kill
- W-Monster = https://wiki.leagueoflegends.com/en-us/Monster
- W-Jungling = https://wiki.leagueoflegends.com/en-us/Jungling
- W-Blue = https://wiki.leagueoflegends.com/en-us/Blue_Sentinel
- W-Red = https://wiki.leagueoflegends.com/en-us/Red_Brambleback
- W-Gromp = https://wiki.leagueoflegends.com/en-us/Gromp
- W-Wolf = https://wiki.leagueoflegends.com/en-us/Murk_Wolf
- W-Raptor = https://wiki.leagueoflegends.com/en-us/Raptor
- W-Krug = https://wiki.leagueoflegends.com/en-us/Krug
- W-Scuttler = https://wiki.leagueoflegends.com/en-us/Rift_Scuttler
- W-Insight = https://wiki.leagueoflegends.com/en-us/Crest_of_Insight
- W-Cinders = https://wiki.leagueoflegends.com/en-us/Crest_of_Cinders
- W-Atlas = https://wiki.leagueoflegends.com/en-us/World_Atlas
- W-Compass = https://wiki.leagueoflegends.com/en-us/Runic_Compass
- W-BoW = https://wiki.leagueoflegends.com/en-us/Bounty_of_Worlds
- W-GoldIncome = https://wiki.leagueoflegends.com/en-us/Gold_income
- W-RoleQuest = https://wiki.leagueoflegends.com/en-us/Role_Quest
- W-Pet = https://wiki.leagueoflegends.com/en-us/Gustwalker_Hatchling
- W-SR = https://wiki.leagueoflegends.com/en-us/Summoner%27s_Rift
- W-V26.01 = https://wiki.leagueoflegends.com/en-us/V26.01
- R-26.1 = https://www.leagueoflegends.com/en-us/news/game-updates/patch-26-1-notes/
- R-25.S1.1 = https://www.leagueoflegends.com/en-us/news/game-updates/patch-25-s1-1-notes/
- R-26.7 = https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-7-notes/
- R-Preview = https://www.leagueoflegends.com/en-us/news/dev/dev-2026-season-one-gameplay-preview/

---

## A. Lane minions

| id | fact | value | source URL | status |
|---|---|---|---|---|
| A1a | First wave spawn (game clock) | 0:30 (was 1:05 before V26.01). Minions within a wave spawn 0.792 s apart | W-Minion; R-26.1 ("Minion spawn: 1:05 -> 30 seconds") | fetched x2 |
| A1b | Wave interval | 30 s from 0:30; 25 s from 14:00 (sequence 13:30 / 14:00 / 14:25); 20 s from 30:00 (sequence 29:25 / 29:50 / 30:10) | W-Minion; R-26.1 | fetched x2 |
| A1c | When waves first meet per lane | Not stated on any fetched page. Related facts only: first-wave top/bot minions ghosted 28 s, mid 18 s; sidelane speed buff (A3b) exists so opposing waves meet at lane midpoint | W-Minion | unverified (no source; from memory under the old 1:05 clock, mid met about 27 s and side lanes about 37 s after spawn; do not rely on it) |
| A2a | Wave composition, spawn order | Super (if any), 3 melee, siege (if any), 3 caster | W-Minion | fetched |
| A2b | Siege (cannon) cadence | Never on super waves. First at 1:30 (wave 3). One every 3 waves until 14:00; every 2 waves after 14:00; every wave after 25:00. Page's listed sequences: "12:00 / 13:30 / 14:25 / 15:15" and "24:25 / 25:15 / 25:40" | W-Minion; W-Siege; R-26.1 (first cannon wave 4 -> wave 3) | fetched x2 |
| A2c | Wave shrink rules | After 14:00: one fewer melee on waves that contain a siege minion. After 30:00: one fewer caster per wave | W-Minion; R-26.1; R-Preview | fetched x2 |
| A2d | Super minions | Spawn in a lane while that lane's enemy inhibitor is down, replace the siege minion, at front of wave. 1 per lane; 2 per lane when all three inhibitors are down. Stop spawning two waves before the inhibitor respawns | W-Super; W-Minion | fetched |
| A3a | Base movement speed | "350 / 375 / 400 / 425 / 450 (based on minutes)". Base raised 325 -> 350 in V26.01 | W-Minion; R-26.1 | fetched x2 |
| A3a2 | Minutes at which each speed tier applies | Not stated in current text. V25.S1.1 history entry says the tiers begin upgrading at 11:00 instead of 10:00 | W-Minion (history) | start 11:00 fetched; later thresholds unverified, from memory (5-minute steps: 11/15/20/25 is a guess) |
| A3b | Sidelane speed-up (top and bot only) | From wave 2 until 14:00: wave 2 spawns with +111 MS, each later wave 4.5 less. Bonus removed in four stages of 7, 7, 7, 4 s (25 s total), each stage end removes 15 MS | W-Minion | fetched |
| A3c | Attack range | Melee 110; caster 550; siege 300; super 170 | W-Melee; W-Caster; W-Siege; W-Super | fetched |
| A3d | Acquisition range | 500 units; 1000 for call-for-help (ally champion attacked by enemy champion) | W-Minion | fetched |
| A3e | Sight range | Not stated on any fetched page | none | unverified, from memory (about 1200 units) |
| A4a | Upgrade cadence | First upgrade at 0:30, then every 90 s regardless of spawns; adds health and AD (melee also armor) up to a cap | W-Minion; W-Melee | fetched |
| A4b | Melee minion stats | HP 465 - 1550; AD 11 - 80; AS 1.25; armor 0 - 20; MR 0; +2% of target current HP on-hit vs lane minions | W-Melee (newest entry V26.09: HP cap 1500 -> 1550) | fetched |
| A4c | Caster minion stats | HP 284 - 600; AD 21 - 125; AS 0.667; armor 0; MR 0; +3.5% target current HP on-hit vs lane minions (was 4% before V26.09) | W-Caster | fetched |
| A4d | Siege minion stats | HP 835 - 5850; AD 37.5 - 126 (+1.5 per upgrade, +4 per upgrade from wave 15); AS 1.00; armor 0; MR 0; +5% target current HP vs lane minions (was 6% before V26.09) | W-Siege; R-26.1 ("Cannon AD: 39, +1.5 every 90 seconds, then +4 from wave 15") | fetched x2 for AD growth; HP range fetched once, see conflicts |
| A4e | Super minion stats | HP 1600 - 7500; AD 185 - 480; AS 0.85; armor 100; MR -30; aura +35 armor and +35 MR to nearby non-super minions | W-Super | fetched (page internally inconsistent on AD, see conflicts) |
| A4f | Per-upgrade HP/AD growth per type | Not listed (only min-max ranges). Riot's V25.S1.1 notes give time spans: melee HP 465-1500 over min 1-48, armor 0-20 over min 1-42, AD 11-80 over min 1-42; ranged HP 284-600 over min 1-56, AD 21-125 over min 1-45; cannon and super scaling stops at 90 min | R-25.S1.1 | fetched (spans only; per-upgrade increments unverified) |
| A4g | Minion damage vs champions and structures | 60% damage | W-Minion; W-Melee | fetched |
| A4h | Minion damage vs turrets | 60% (was 55%); siege 84% (was 82.5%); mid-lane siege +30% attack speed while attacking turrets | R-26.1; W-Siege | fetched x2 |
| A4i | Super minion vs non-turret structures | 12.5% damage | W-Super | fetched |
| A4j | Turret damage to minions (per shot, % of minion max HP, pre-mitigation) | Melee 45%; caster 70%; siege 14% / 11% / 8% by turret tier; super 7% | W-Melee; W-Caster; W-Siege; W-Super | fetched |
| A4k | Minion pushing advantage | Bonus damage to enemy minions = (5% + 5% x turret advantage) x level advantage, max 60%; flat damage reduction = 1 + turret advantage x level advantage, max 10; level advantage capped at 3; starts at 3:30 | W-Minion | fetched |
| A5a | Gold per minion | Melee 20 (was 21); caster 14; siege 50 + 1 per upgrade (was 60 + 3 per 90 s); super 50 + 1 per upgrade | W-Melee; W-Caster; W-Siege; W-Super; R-26.1 | fetched x2 |
| A5b | XP per minion (solo, 100%) | Melee 62 (was 65); caster 31 (was 32); siege 75 (was 100); super 75 (was 100). No growth over time listed | same as A5a | fetched x2 |
| A5c | Average wave gold (wiki table, V26.01) | 0:30: 118.66 per wave (18.7 per CS); 14:00: 115 (19.16); 15:00: 121.5 (20.25); 25:00: 148 (24.66); 30:00: 137 (27.4) | W-Minion | fetched |
| A5d | Minion XP comeback bonus | Only once enemy minions reach level 6: champions more than 1 level below the minion get +20% XP, rising to a maximum of +240% at 6 levels below | W-XP | fetched (the intermediate steps were reported inconsistently) |
| A6a | Minion XP range | 1500 units from the minion's death location (was 1400 before V25.S1.1) | W-Minion; W-XP; R-25.S1.1 | fetched x2 |
| A6b | Minion XP split | Per-champion share of base XP by number of sharing champions 1 / 2 / 3 / 4 / 5 / 6: 100 / 65 / 43.3 / 32.5 / 26 / 21.7%. So solo = 100%, any shared kill = about 130% total split equally. Before V26.01: 95 / 62 / 41.3 / 31 / 24.8 / 20.7% (solo 95%, shared 124%) | W-XP; W-Minion; R-26.1 | fetched x2 |

## B. Jungle camps (ordinary)

| id | fact | value | source URL | status |
|---|---|---|---|---|
| B7a | Camp grouping per quadrant | Blue-buff quadrant: Blue Sentinel, Gromp, Murk Wolves. Red-buff quadrant: Red Brambleback, Raptors, Krugs. Both jungles hold the same six camps, "mirrored across the river" | https://www.thespike.gg/league-of-legends/beginner-guides/how-to-jungle-guide (updated 2026-10-19); W-Jungling | fetched |
| B7b | Which quadrant is top-side or bot-side for each team | Blue team: blue-buff quadrant is top-side (west, between top and mid), red-buff quadrant is bot-side (south). Red team: red-buff quadrant is top-side (north), blue-buff quadrant is bot-side (east). Point symmetry about map centre | No fetched page states this in text (wiki camp pages show it only as map images). Partial support on W-SR: Raptor nest "in the south", a Gromp statue "in the northeast, near the red team's Gromp camp"; Baron pit in top half, Dragon pit in bottom half | unverified, from memory (layout has been stable since 2014) |
| B8a | Initial spawn: Blue Sentinel, Red Brambleback, Murk Wolves, Raptors | 0:55 (was 1:30 before V26.01) | W-Blue; W-Red; W-Wolf; W-Raptor; R-26.1 | fetched x2 |
| B8b | Initial spawn: Gromp, Krugs | 1:07 (was 1:42 before V26.01) | W-Gromp; W-Krug; R-26.1 | fetched x2 |
| B9a | Respawn delay: Blue Sentinel, Red Brambleback | 5:00 (300 s) | W-Blue; W-Red; R-26.1 Swiftplay section cites base "300s" | fetched x2 |
| B9b | Respawn delay: Gromp, Murk Wolves, Raptors, Krugs | 2:15 (135 s) | W-Gromp; W-Wolf; W-Raptor; W-Krug; R-26.1 Swiftplay section cites base "135s" | fetched x2 |
| B9c | What starts the countdown | Timer starts when every monster in the camp is dead ("does not start until all monsters in the camp are dead"); camp then stays empty for its respawn time and all monsters reappear. So respawn = (game time of last monster's death) + delay. If the large monster dies and small ones survive, the leftovers are auto-killed 10 s after returning to neutral state | W-Monster (Respawn section) | fetched |
| B10a | Blue Sentinel | Gold 90; XP 95 - 142.5 (by monster level); HP 2300 - 6210 (by level) | W-Blue | fetched |
| B10b | Red Brambleback | Gold 90; XP 95 - 142.5; HP 2300 - 6210; AD 66 - 198; armor 42; MR 42 | W-Red | fetched |
| B10c | Gromp | Gold 80; XP 120 - 180; HP 2050 - 4817.5 | W-Gromp | fetched |
| B10d | Murk Wolves (1 Greater + 2 Murk Wolves) | Greater: 55 gold, 50 - 75 XP, HP 1600 - 3760. Each small: 15 gold, 15 - 22.5 XP, HP 630 - 1480.5. Camp total: 85 gold, 80 - 120 XP, 2860 HP at level 1 | W-Wolf | per-monster fetched; totals fetched (derived) |
| B10e | Raptors (1 Crimson + 5 Raptors) | Crimson: 35 gold, 20 - 30 XP, HP 1200 - 2820. Each small: 8 gold, 10 - 15 XP, HP 500 - 1175. Camp total: 75 gold, 70 - 105 XP, 3700 HP at level 1 | W-Raptor | per-monster fetched; totals fetched (derived) |
| B10f | Krugs (Ancient Krug + Krug; Ancient spawns 4 Mini Krugs, Krug spawns 2; 8 units total) | Ancient: 15 gold, 15 - 22.5 XP, HP 1350 - 3172.5. Krug: 10 gold, 10 - 15 XP, HP 650 - 1527.5. Mini: 14 gold, 16 - 24 XP, HP 60 - 141. Camp total: 109 gold, 121 - 181.5 XP, about 2360 HP at level 1. Spawned minis are one level lower | W-Krug | per-monster fetched; totals fetched (derived) |
| B10g | Level scaling rule | Camp level = average of all champions' levels at the moment the camp spawns, rounded to nearest integer. Level raises health, damage, XP (gold is flat for these camps). Caps differ per camp. Per-level tables are not on the fetched pages (only min - max) | W-Monster; W-Jungling | fetched (per-level curve unverified) |
| B10h | Jungle-item bonus on large monsters | +80 XP per large monster always, +150 more for the first large monster killed; first camp always gives level 2. After jungle quest: +10 gold and +10 XP per camp | W-Pet; W-Jungling; W-RoleQuest | fetched |
| B11 | Typical full-clear time | No reputable source for the 2026 clock was found. Third-party guides say "a clean full clear finishes around 3:15 to 3:30", but the same guide still says Scuttler spawns at 3:30, i.e. it is on the pre-2026 clock (camps at 1:30). Shifting by the 35 s rule gives roughly 2:40 - 2:55, which is an inference, not a sourced number. Riot also said it is "slightly lowering the speed of early game clears" in 2026 | https://www.dodge.gg/en-US/lol/news/jungle-guide-2026 (stale clock); R-Preview | approximate, unverified for 2026 |
| B12a | Blue buff (Crest of Insight) | Duration 120 s. Ability haste 10 / 15 / 20 by level (V26.14; was flat 10). Mana/energy regen: page lists "5% of max mana + 25 every 5 seconds". Holder only; transfers to the killing enemy champion with refreshed duration | W-Insight | fetched (regen wording ambiguous on the page) |
| B12b | Red buff (Crest of Cinders) | Duration 120 s. On-hit slow for 3 s: melee 10 / 15 / 25%, ranged 5 / 7.5 / 12.5% by level; burn 15 - 60 total true damage over 3 ticks; out-of-combat regen 0.5 / 1 / 1.5 / 3% max HP per 5 s. Holder only; transfers on champion kill | W-Cinders | fetched (page's own V26.01 entry says melee slow max 20% and burn max 54) |
| B12c | Buffs no longer team-wide | The "Voidborn buff camp grants buff to all living allies after Baron spawns" rule was removed in V26.01 | W-Blue; W-Red; R-26.1 | fetched x2 |

## C. Rift Scuttler

| id | fact | value | source URL | status |
|---|---|---|---|---|
| C13a | Initial spawn | 2:55 (was 3:30 before V26.01) | W-Scuttler; R-26.1 | fetched x2 |
| C13b | Count and location | Two at first spawn: one in the top half of the river, one in the bottom half | W-Scuttler | fetched |
| C13c | Respawn | 2:30 (150 s). Both initial Scuttlers must be killed before the respawn timer starts. After that only one Scuttler can be on the map at a time for the rest of the game; respawn location is random (top or bottom river) and shown ahead of time by a respawn marker | W-Scuttler | fetched |
| C13d | Later-game change | When Baron spawns at 20:00 all Scuttlers become permanently Voidborn: on death a void aura reveals enemy champions 3 s, non-champions 12 s, sets revealed wards to 1 HP. No extra health (wiki calls this a bug) | W-Scuttler | fetched |
| C14a | Gold | 55 - 121, by monster level | W-Scuttler | fetched |
| C14b | XP | 100 - 150, by monster level. Spawns at the average champion level; no longer spawns at level -1 (V26.01) | W-Scuttler; R-26.1 | fetched x2 |
| C14c | First-spawn modifiers | First-spawned Scuttlers: 35% less health (1007.5 - 3425.5 vs normal 1550 - 5270) and, per the wiki, "80% less XP" | W-Scuttler | fetched (the 80% XP figure looks stale next to the V26.01 note; treat as doubtful) |
| C15a | Speed Shrine duration | 90 s, spawned in the centre of the river section where she died | W-Scuttler | fetched |
| C15b | Shrine vision | Killer's team gets sight over a 525 radius | W-Scuttler | fetched |
| C15c | Shrine speed | Untargetable 500-radius zone; champions inside gain 30% bonus MS for 1.5 s if they have not damaged a non-plant in the last 5 s; dealing or taking damage ends it | W-Scuttler | fetched |
| C15d | Who benefits from speed | Page says "champions" crossing it and does not say enemies are excluded | W-Scuttler | fetched as ambiguous; unverified, from memory: only the killer's team gets the speed |

## D. Public timer rules

| id | fact | value | source URL | status |
|---|---|---|---|---|
| D16a | First spawn | "The first spawn of all non-epic camps is calculated automatically for both teams" | W-Jungling | fetched |
| D16b | Team that saw the clear | If a team had vision of a non-epic camp when it was cleared, the camp icon is replaced by an accurate respawn timer for that team | W-Jungling; W-Monster | fetched x2 |
| D16c | Team that did not see the clear | Gets nothing ("no way to know an enemy was recently there") until it gains sight of the camp location inside a window before respawn: 60 s for Blue Sentinel and Red Brambleback; 10 s for Gromp, Krugs, Murk Wolves, Raptors. Sight gained earlier than the window gives no information | W-Jungling; W-Monster | fetched x2 |
| D16d | Does the enemy team get it | Same rule applies per team: only via vision of the clear or vision inside the 60 s / 10 s window | W-Jungling | fetched |
| D16e | Display | Minimap hourglass icon: grey at 60 s remaining, yellow/filled at 10 s. With scoreboard open: text M:SS timers (yellow at 10 s). Option "Enable All Camp Timers" (Settings > Interface) shows text timers always. Timers cap at 2 minutes, displayed "2m+". Known Blue/Red buff timers also show at top of screen with the scoreboard open | W-Jungling | fetched |
| D16f | Epic camps | Deaths announced to both teams; both always get exact timers | W-Jungling; W-Monster | fetched x2 |
| D16g | Rift Scuttler timer | Wiki only says the respawn location is "signaled ahead of time with a marker"; no vision rule or lead time is stated. Scuttler is not listed in the 60 s / 10 s window list | W-Scuttler; W-Jungling | unverified (rule not documented on fetched pages) |

## E. Economy

| id | fact | value | source URL | status |
|---|---|---|---|---|
| E17a | Starting gold | 500 | W-Gold; R-26.1 Swiftplay section ("Starting Gold: 500g => 1400g" for Swiftplay) | fetched x2 |
| E17b | Passive gold | 20.4 gold per 10 s, applied every 0.5 s, starting at 1:05 (was 1:40 before V26.01, 1:50 before V25.S1.1) | W-Gold; W-V26.01; R-26.1 ("Ambient gold start: 65 seconds") | fetched x2 for start time; rate fetched once |
| E18a | Champion kill gold (base bounty by victim level) | Levels 1 - 6: 300; level 7: 310; +10 per level to 420 at level 18. First Blood +100 (reinstated V26.01). Minimum kill value 50. Single kill capped at base + 700 | W-Bounty | fetched |
| E18b | Assist gold | Assist pool = half the kill bounty paid, capped at 50% of base (150 at level 1 to 210 at level 18), split equally among assistors. Early game the pool is 50% - 100% by game time (breakpoints not stated) | W-Bounty | fetched; breakpoints unverified |
| E18c | Bounty rule, positive | Bounty grows 1 per 3 gold earned from kills/assists and 1 per 20 gold from minions, monsters and support-item income. 100-gold buffer before a shutdown shows; shutdown = bounty above base + 100. Shutdown gold is cut 30 / 60 / 90 / 100% after 6:00 for teams not convincingly winning | W-Bounty | fetched |
| E18d | Bounty rule, negative | On death the victim's bounty drops 1 per 3.5 gold paid out (V26.03); floor 50. While negative, it recovers 1 per 7 gold of minion/monster income (V26.03). Changes apply 5 s after leaving champion combat | W-Bounty | fetched |
| E18e | Kill XP | Solo: 42 to 990 XP by victim level; shared: 27.97 to 891 XP total split equally among eligible allies (killer, assistors, allies within 1600 units). +/-20% per full level of difference beyond the first; floor 40% when killing lower-level champions. No per-level table on the page | W-XP | fetched (endpoints only) |
| E19 | XP per level | See table below. Cap 18 by default; 20 for a player who completes the Top Lane Role Quest | W-XP; R-26.1 ("level cap 20") | fetched x2 for the cap; table fetched once |
| E20a | Support item line | World Atlas (400 gold, auto-purchased for the drafted Support in permanent SR queues) -> Runic Compass -> Bounty of Worlds -> one of Bloodsong, Celestial Opposition, Dream Maker, Solstice Sleigh, Zaz'Zak's Realmspike | W-Atlas; W-BoW | fetched |
| E20b | Passive gold per 10 s | World Atlas 3; Runic Compass 5; Bounty of Worlds 5; final upgrades 9 (was 5 before V26.01) | W-Atlas; W-Compass; W-BoW; W-GoldIncome; R-26.1 | fetched x2 |
| E20c | Shared Riches charges | Max 3 charges, 1 charge per 20 s, first charge at 1:05. Needs an allied champion within 1050 units | W-Atlas; W-Compass | fetched |
| E20d | Minion sharing | Using a charge on a minion kill: support gets 18 gold (World Atlas) or 21 (Runic Compass) and the nearest allied champion gets the minion's kill gold. Basic attack executes minions below 50% max HP (melee) or 30% (ranged) if a charge is available | W-Atlas; W-Compass; W-RoleQuest | fetched x2 |
| E20e | Poke | Damaging an enemy champion or structure with an attack or ability consumes one charge: 18 gold (World Atlas) or 21 (Runic Compass), same for melee and ranged since V26.16 | W-Atlas; W-Compass; W-RoleQuest | fetched x2 |
| E20f | Quest thresholds | Support Role Quest = 800 points, 1 point per gold earned through World Atlas / Runic Compass (charges plus the item's gold-per-10). Item pages: 400 gold earned upgrades World Atlas to Runic Compass; 800 upgrades Runic Compass to Bounty of Worlds. Reward also: Control Ward costs 40 gold, stored in the quest slot | W-RoleQuest; W-Atlas; W-Compass | fetched (whether 800 is cumulative or counted after the first 400 is not explicit) |
| E20g | Wiki's sustained rates (gold per 10 s, excluding base) | World Atlas: passive 3, minion sharing 10.5, ranged poke 13, melee poke 14. Runic Compass: 5, 15, 16, 17. Time to finish a 400-gold stage: World Atlas 22.2 min passive / 6.3 sharing / 5.1 ranged poke / 4.8 melee poke | W-GoldIncome | fetched (table may predate the V26.16 change to 18/21 gold) |
| E20h | Support farming penalty | Riot 26.7: "we're now completely disabling the reduction in gold" for supports killing many minions. Wiki pages still print the old rule: before 5:00, 24 or more minion kills (divided by support items on team) cut minion gold 80%; after 5:00, 6 per minute cut it 50 - 80% | R-26.7; W-Atlas; W-Compass; W-BoW | fetched; conflict, see below. Riot notes say the penalty is off as of 26.07 |
| E20i | Support off-lane penalty | 33% reduced gold and XP from minions (and from support quest items) outside bot lane until level 5 (V26.16; was 25% until level 3) | W-RoleQuest | fetched |
| E20j | One support item per team | Since V25.09, matchmade SR queues stop more than one player buying a support item | W-GoldIncome | fetched |
| E21a | Jungle item, lane minion penalty | 450 gold, requires Smite. Minion XP reduced 70% at game start, scaling to 0% by 20:00 (paused while more than 1.5 levels behind average). "Monster Hunter": if minion gold exceeds 40% of monster gold, minion kills give 13 less gold and 50% less XP; removed at 14:00 | W-Pet; W-XP | fetched x2 |
| E21b | Jungle item, pet stacks | 1 treat per large monster kill; bonus treat stored every 60 s from 1:30 (first at 2:30), consumed on a large monster kill for an extra treat and +20 gold. Evolves at 15 treats (Unleashed Smite) and 35 treats (Primal Smite, quest complete; was 20 / 40 before V26.01). Comeback: +50 XP per level behind when more than 1.1 levels below average | W-Pet; W-RoleQuest; R-26.1 | fetched x2 |

### E19. XP required per champion level (Summoner's Rift)

Source: W-XP, fetched. Formula visible in the table: XP to reach level L from L-1 = 280 + 100 x (L - 2).

| level | XP for this level | cumulative XP |
|---|---|---|
| 1 | 0 | 0 |
| 2 | 280 | 280 |
| 3 | 380 | 660 |
| 4 | 480 | 1,140 |
| 5 | 580 | 1,720 |
| 6 | 680 | 2,400 |
| 7 | 780 | 3,180 |
| 8 | 880 | 4,060 |
| 9 | 980 | 5,040 |
| 10 | 1,080 | 6,120 |
| 11 | 1,180 | 7,300 |
| 12 | 1,280 | 8,580 |
| 13 | 1,380 | 9,960 |
| 14 | 1,480 | 11,440 |
| 15 | 1,580 | 13,020 |
| 16 | 1,680 | 14,700 |
| 17 | 1,780 | 16,480 |
| 18 | 1,880 | 18,360 |
| 19 (top quest only) | 1,980 | 20,340 |
| 20 (top quest only) | 2,080 | 22,420 |

---

## Rules changed in the last two seasons that older knowledge gets wrong

| change | old | now (26.22) | patch | source | status |
|---|---|---|---|---|---|
| Whole early clock moved 35 s earlier | minions 1:05, buffs/wolves/raptors 1:30, gromp/krugs 1:42, scuttler 3:30, passive gold 1:40 | 0:30, 0:55, 1:07, 2:55, 1:05 | V26.01 | R-26.1; R-Preview | fetched x2 |
| Wave interval is no longer constant | 30 s all game | 30 s, then 25 s from 14:00, 20 s from 30:00, with one fewer melee on cannon waves (mid game) and one fewer caster (late) | V26.01 | R-26.1; W-Minion | fetched x2 |
| First cannon wave | wave 3 (pre-2025), wave 4 (2025) | wave 3 at 1:30 | V25.S1.1 then V26.01 | R-25.S1.1; R-26.1 | fetched |
| Minion XP sharing | solo 95%, shared 124% total; range 1400 | solo 100%, shared 130% total; range 1500 | V25.S1.1 (range), V26.01 (split) | W-XP; R-26.1 | fetched x2 |
| Minion bounties | melee 21 g / 65 XP; caster 32 XP; cannon 60 + 3 per 90 s gold / 100 XP | 20 g / 62 XP; 31 XP; 50 + 1 per upgrade / 75 XP | V26.01 | R-26.1 | fetched x2 |
| Minions vs minions | flat AD only | on-hit bonus of 2% / 3.5% / 5% of target current HP (melee / caster / siege) | V25.S1.1, tuned V26.09 | W-Melee; W-Caster; W-Siege | fetched |
| Minion damage to champions and turrets | 50% | 60% (siege 84% to turrets) | V25.S1.1 (55%), V26.01 (60%) | R-25.S1.1; R-26.1 | fetched |
| Minion base move speed | 325 | 350 | V26.01 | R-26.1 | fetched x2 |
| Role quests exist | none | Top / Jungle / Mid / Bot / Support quests, tracking from 1:05; mid and support take a minion gold/XP penalty when out of lane early | V26.01, retuned V26.09 and V26.16 | W-RoleQuest; R-26.1 | fetched x2 |
| Level cap | 18 | 18, or 20 after the Top Lane quest | V26.01 | W-XP; R-26.1 | fetched x2 |
| Atakhan and Feats of Strength | added in 2025 | removed | V26.01 | R-26.1; W-V26.01 | fetched x2 |
| Baron spawn | 20:00 (2024), 25:00 (2025) | 20:00 | V26.01 | R-26.1 | fetched |
| First Blood bonus | +100, removed in 2025 | +100 again | V25.S1.1, V26.01 | W-Bounty | fetched |
| Kill base gold | flat 300 | 300 to 420 by victim level | V25.09 | W-Bounty | fetched |
| Team-wide buffs after Baron | Voidborn Blue/Red gave the buff to all living allies | removed; killer only | V26.01 | W-Blue; R-26.1 | fetched x2 |
| Jungle pet evolution | 20 / 40 treats | 15 / 35 treats | V26.01 | R-26.1; W-Pet | fetched x2 |
| Scuttler level | spawned at level -1 | spawns at average champion level | V26.01 | R-26.1; W-Scuttler | fetched x2 |
| Support farming gold penalty | throttled after a kill threshold | disabled | V26.07 | R-26.7 | fetched |
| Support Shared Riches gold | 15 / 20 minion, melee 22 / ranged 20 poke | 18 (Atlas) / 21 (Compass) for everything | V26.16 | W-Atlas; W-Compass; W-RoleQuest | fetched |
| Final support items passive gold | 5 per 10 s | 9 per 10 s | V26.01 | R-26.1 | fetched |
| Outer turret gold | 250 local gold on kill | 0 local kill gold; plates at 10/25/45/70/100% missing HP; plate gold drops 10 per minute from minute 11 (cap -40); first turret +300 to nearby players; inner and inhibitor turrets now have plates | V26.01 | R-26.1 | fetched (out of requested scope, listed because it shifts the gold curve) |

## Conflicts and gaps

1. **When waves first meet in each lane (A1c):** not documented on any fetched page. Needs in-game measurement or a derived value from spawn point distance and 350 MS plus the sidelane speed buff.
2. **Per-upgrade minion growth (A4f):** the wiki gives only min - max ranges. Riot's V25.S1.1 notes give minute spans, which allow a linear fit but are not per-upgrade numbers. Siege HP conflicts: wiki "835 - 5850", Riot V25.S1.1 "920 - 2960 (min 2:30 - 38)"; these likely measure different spans (wiki to the 90-minute cap).
3. **Super minion AD:** the wiki infobox says 185 - 480, its V25.S1.1 entry says 215 - 510, and V26.01 says base 210 -> 180. Internally inconsistent.
4. **Minion sight range (A3e) and the minutes of the 350/375/400/425/450 speed tiers (A3a2):** not found.
5. **Quadrant placement (B7b):** camp grouping is sourced, but no fetched page states in text which quadrant is top-side or bot-side for each team. From memory only.
6. **Full-clear time (B11):** every guide found uses the pre-2026 clock or gives no clock time. No sourced 2026 benchmark.
7. **Camp XP per level and total HP per level (B10):** only min - max ranges; the level-to-value curve and level caps are not on the fetched pages. Camp totals are my sums.
8. **Scuttler respawn timer visibility (D16g)** and whether enemies get the shrine speed (C15d): not documented on fetched pages. First-spawn "80% less XP" may be stale.
9. **Support farming penalty (E20h):** Riot 26.7 notes say the gold reduction is completely disabled; World Atlas and Bounty of Worlds wiki pages still print threshold rules, while Runic Compass says removed. Trust Riot.
10. **Support quest threshold (E20f):** Role Quest page says 800 points; item pages say 400 then 800. Unclear whether the 800 is cumulative.
11. **Red buff numbers (B12b):** page body says melee slow max 25% and burn max 60; its own V26.01 entry says 20% and 54. Blue buff regen wording is ambiguous.
12. **Kill XP (E18e):** only endpoints (42 - 990 solo); no per-level table. Early-game assist-gold breakpoints (E18b) not stated.
13. **Patch stamp:** the wiki does not label which patch a page reflects. Minion, Gold and Crest pages show edits through mid/late 2026 but the Minion page carries an "outdated" notice.
14. **Swiftplay contamination risk:** the tail of Riot's 26.1 notes lists Swiftplay-only values (camp respawn 270 s / 120 s, starting gold 1400, start level 3, cannon every wave from wave 3). These are not ranked/normal SR values.
15. **Fetch fidelity:** every value passed through a summarizing fetch tool. Rows marked "fetched x2" were seen on two pages; single-source rows deserve a spot check before being hard-coded.
