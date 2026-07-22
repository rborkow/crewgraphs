"""CrewGraphs phase-zero cohort: 10 US rowing-club nonprofits.

EINs are stored as 9-digit zero-padded strings. `racing_name` is the identity a
rower would recognize; `legal_name` is the IRS filer of record. Where those
differ, that is a deliberate structural-identity test case, not an error.

Re-runnable: this module is imported by the fetch/extract/crosscheck scripts.
"""

COHORT = [
    # slot, ein, racing_name, expected legal_name, city, state, notes
    dict(slot=1,  ein="237397498", racing_name="Vesper Boat Club",
         legal_name="Vesper Boat Club Inc", city="Philadelphia", state="PA",
         notes="c3; historic Schuylkill Navy club"),
    dict(slot=2,  ein="232744491", racing_name="Undine Barge Club",
         legal_name="The Undine Barge Club Of Philadelphia", city="Conshohocken", state="PA",
         notes="c3 N50Z; mailing addr is agent/treasurer in Conshohocken, boathouse in Philadelphia"),
    dict(slot=3,  ein="530127820", racing_name="Potomac Boat Club",
         legal_name="Potomac Boat Club", city="Washington", state="DC",
         notes="501(c)(7) SOCIAL CLUB - contributions concept differs from c3"),
    dict(slot=4,  ein="042863756", racing_name="Community Rowing, Inc.",
         legal_name="Community Rowing Inc", city="Brighton", state="MA",
         notes="c3; largest community rowing org in US; 44 name-collision hits in search"),
    dict(slot=5,  ein="113632924", racing_name="Row New York",
         legal_name="Row New York Inc", city="New York", state="NY",
         notes="c3 N67"),
    dict(slot=6,  ein="331055179", racing_name="Saugatuck Rowing Association",
         legal_name="Olympic Athletes Rowing At Saugatuck Inc", city="Westport", state="CT",
         notes="HARD CASE: racing brand 'Saugatuck Rowing' is entangled with a for-profit club; "
               "the nonprofit filer is 'Olympic Athletes Rowing At Saugatuck' (OARS). "
               "Documented alternate: Marin Rowing Association EIN 237448092 (Greenbrae CA)."),
    dict(slot=7,  ein="363508216", racing_name="Lincoln Park Boat Club",
         legal_name="Lincoln Park Boat Club", city="Chicago", state="IL",
         notes="501(c)(4) social welfare; SEPARATE c3 arm 'Lincoln Park Boat Club Charitable Outreach' "
               "EIN 272334832 -> two-entity structure"),
    dict(slot=8,  ein="742219650", racing_name="Austin Rowing Club",
         legal_name="Austin Rowing Club", city="Austin", state="TX",
         notes="c3 N67Z"),
    dict(slot=9,  ein="030388282", racing_name="Concord Crew (booster)",
         legal_name="Friends Of Concord Crew", city="Concord", state="NH",
         notes="SCHOLASTIC BOOSTER; long 990-EZ filing history (data 2012-2023) -> EZ concept-matrix test"),
    dict(slot=10, ein="811495108", racing_name="Washington Rowing / Husky Crew",
         legal_name="Husky Rowing Foundation", city="Seattle", state="WA",
         notes="UNIVERSITY-SUPPORT FOUNDATION; racing identity != filer. No 'Washington Rowing Foundation' "
               "entity exists (search=0); real filer is 'Husky Rowing Foundation'. Appears 990-N-only "
               "(no structured data) -> coverage-hole exemplar"),
]

# Documented alternates encountered during resolution (not in the primary 10).
ALTERNATES = [
    dict(ein="237448092", legal_name="Marin Rowing Association", city="Greenbrae", state="CA",
         notes="Fallback for slot 6 if Saugatuck resolved badly; resolved cleanly as c3 N67Z"),
    dict(ein="272334832", legal_name="Lincoln Park Boat Club Charitable Outreach", city="Chicago", state="IL",
         notes="c3 charitable arm related to slot 7 (a c4)"),
]

EINS = [o["ein"] for o in COHORT]
