-- migrate:up

-- Metric definitions are versioned product content (PRD §7): seeded by
-- migration so every change is code-reviewed, never job-written.
INSERT INTO core.metric_definition (metric_key, version, label, description, unit, eligibility_rule, limitation, status) VALUES
('operating_margin', 1, 'Operating margin',
 '(Total revenue − total expenses) ÷ total revenue, per fiscal year.',
 'percent',
 '{"requires_positive": ["total_revenue"]}',
 'A single year can swing on one-time gifts or capital projects; not a health grade.',
 'active'),
('revenue_cagr', 1, 'Revenue growth (CAGR)',
 'Compound annual growth rate between the earliest and latest comparable total-revenue observations in the selected window.',
 'percent',
 '{"min_observations": 3}',
 'Requires at least three comparable annual filings; window boundaries are disclosed with the value.',
 'active'),
('contribution_dependency', 1, 'Contribution dependency',
 'Contributions and grants ÷ total revenue, per fiscal year.',
 'percent',
 '{"requires_positive": ["total_revenue"]}',
 'Clubs classify member income differently; compare within similar program types.',
 'active'),
('program_service_share', 1, 'Program service share',
 'Program service revenue ÷ total revenue, per fiscal year.',
 'percent',
 '{"requires_positive": ["total_revenue"]}',
 'Membership and entry fees may be reported as program service revenue or dues depending on the club.',
 'active'),
('compensation_intensity', 1, 'Compensation intensity',
 'Salaries and benefits ÷ total expenses, per fiscal year.',
 'percent',
 '{"requires_positive": ["total_expenses"]}',
 'Reflects all reported compensation, not coaching payroll specifically.',
 'active'),
('membership_dues_share', 1, 'Membership dues share',
 'Membership dues ÷ total revenue, per fiscal year.',
 'percent',
 '{"requires_positive": ["total_revenue"], "requires_resolved": ["membership_dues"]}',
 'The dues line is optional on Form 990; many clubs report member income as program service revenue instead.',
 'active');

-- migrate:down

DELETE FROM core.metric_definition WHERE version = 1 AND metric_key IN
('operating_margin','revenue_cagr','contribution_dependency','program_service_share','compensation_intensity','membership_dues_share');
