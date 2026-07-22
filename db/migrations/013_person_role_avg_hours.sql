-- migrate:up

-- Part VII reports average hours per week per person; the extractor already
-- stages it but core.person_role had nowhere to land it. Hours are a rate
-- (e.g. 40.00), not money, so this is its own small column rather than
-- another numeric(16,2) compensation field.
ALTER TABLE core.person_role ADD COLUMN avg_hours_week numeric(5,2);

-- migrate:down

ALTER TABLE core.person_role DROP COLUMN avg_hours_week;
