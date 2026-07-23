/**
 * The 24-concept financial catalog as presented on /methods: which XML
 * elements each concept reads on Form 990 and Form 990-EZ.
 *
 * Transcribed from the pipeline's concept map
 * (`pipeline/src/crewgraphs/concept_map/${CONCEPT_MAP_VERSION}.yaml`) — the
 * file that actually drives extraction. A drift guard in
 * `methods-model.test.ts` reads that YAML and fails if this table and the map
 * disagree, so update both together.
 */

export const CONCEPT_MAP_VERSION = "cm-2026.07.1";

export type ConceptGroup = "revenue" | "expenses" | "balance_sheet" | "organization";

export interface ConceptMapEntry {
  key: string;
  label: string;
  group: ConceptGroup;
  /** XML elements read on Form 990; empty means the concept is not on the 990. */
  form990: string[];
  /** XML elements read on Form 990-EZ; empty means "unavailable — not on 990-EZ". */
  form990ez: string[];
  /** How multiple elements combine, or a caveat worth a footnote. */
  note?: string;
}

export const CONCEPT_MAP: ConceptMapEntry[] = [
  {
    key: "total_revenue",
    label: "Total revenue",
    group: "revenue",
    form990: ["CYTotalRevenueAmt"],
    form990ez: ["TotalRevenueAmt"]
  },
  {
    key: "revenue_less_expenses",
    label: "Revenue less expenses",
    group: "revenue",
    form990: ["CYRevenuesLessExpensesAmt"],
    form990ez: ["ExcessOrDeficitForYearAmt"]
  },
  {
    key: "contributions_grants",
    label: "Contributions & grants",
    group: "revenue",
    form990: ["CYContributionsGrantsAmt"],
    form990ez: ["ContributionsGiftsGrantsEtcAmt"],
    note: "On the full 990 this line includes membership dues treated as contributions; on the EZ it does not."
  },
  {
    key: "program_service_revenue",
    label: "Program service revenue",
    group: "revenue",
    form990: ["CYProgramServiceRevenueAmt"],
    form990ez: ["ProgramServiceRevenueAmt"]
  },
  {
    key: "membership_dues",
    label: "Membership dues",
    group: "revenue",
    form990: ["MembershipDuesAmt"],
    form990ez: ["MembershipDuesAmt"],
    note: "An optional line — many clubs report member income as program service revenue instead."
  },
  {
    key: "investment_income",
    label: "Investment income",
    group: "revenue",
    form990: ["CYInvestmentIncomeAmt"],
    form990ez: ["InvestmentIncomeAmt"]
  },
  {
    key: "fundraising_events_gross",
    label: "Fundraising events (gross)",
    group: "revenue",
    form990: ["FundraisingGrossIncomeAmt", "GrossIncomeFundraisingEventsAmt"],
    form990ez: ["FundraisingGrossIncomeAmt"]
  },
  {
    key: "fundraising_events_net",
    label: "Fundraising events (net)",
    group: "revenue",
    form990: ["FundraisingGrossIncomeAmt", "FundraisingDirectExpensesAmt"],
    form990ez: ["SpecialEventsNetIncomeLossAmt"],
    note: "On the full 990 this is computed: gross event income minus direct event expenses."
  },
  {
    key: "other_revenue",
    label: "Other revenue",
    group: "revenue",
    form990: ["CYOtherRevenueAmt"],
    form990ez: ["OtherRevenueTotalAmt"]
  },
  {
    key: "total_expenses",
    label: "Total expenses",
    group: "expenses",
    form990: ["CYTotalExpensesAmt"],
    form990ez: ["TotalExpensesAmt"]
  },
  {
    key: "grants_paid",
    label: "Grants paid",
    group: "expenses",
    form990: ["CYGrantsAndSimilarPaidAmt"],
    form990ez: ["GrantsAndSimilarAmountsPaidAmt"]
  },
  {
    key: "salaries_benefits_total",
    label: "Salaries & benefits",
    group: "expenses",
    form990: ["CYSalariesCompEmpBnftPaidAmt"],
    form990ez: ["SalariesOtherCompEmplBnftAmt"]
  },
  {
    key: "officer_compensation",
    label: "Officer compensation",
    group: "expenses",
    form990: ["CompCurrentOfcrDirectorsGrp/TotalAmt", "CompCurrentOfcrDirectorsAmt"],
    form990ez: ["OfficerDirectorTrusteeEmplGrp/CompensationAmt"],
    note: "On the EZ this is summed across the officer table rather than read from a single line."
  },
  {
    key: "professional_fundraising_fees",
    label: "Professional fundraising fees",
    group: "expenses",
    form990: ["FeesForServicesProfFundraisingGrp/TotalAmt", "FeesForServicesProfFundraising"],
    form990ez: []
  },
  {
    key: "occupancy",
    label: "Occupancy",
    group: "expenses",
    form990: ["OccupancyGrp/TotalAmt"],
    form990ez: ["OccupancyRentUtltsAndMaintAmt"]
  },
  {
    key: "program_service_expense",
    label: "Program service expense",
    group: "expenses",
    form990: ["TotalFunctionalExpensesGrp/ProgramServicesAmt"],
    form990ez: ["TotalProgramServiceExpensesAmt"]
  },
  {
    key: "management_general_expense",
    label: "Management & general expense",
    group: "expenses",
    form990: ["TotalFunctionalExpensesGrp/ManagementAndGeneralAmt"],
    form990ez: []
  },
  {
    key: "fundraising_expense",
    label: "Fundraising expense",
    group: "expenses",
    form990: ["TotalFunctionalExpensesGrp/FundraisingAmt"],
    form990ez: []
  },
  {
    key: "total_assets_eoy",
    label: "Total assets (end of year)",
    group: "balance_sheet",
    form990: ["TotalAssetsEOYAmt", "TotalAssetsGrp/EOYAmt"],
    form990ez: ["Form990TotalAssetsGrp/EOYAmt"]
  },
  {
    key: "total_liabilities_eoy",
    label: "Total liabilities (end of year)",
    group: "balance_sheet",
    form990: ["TotalLiabilitiesEOYAmt", "TotalLiabilitiesGrp/EOYAmt"],
    form990ez: ["SumOfTotalLiabilitiesGrp/EOYAmt"]
  },
  {
    key: "net_assets_eoy",
    label: "Net assets (end of year)",
    group: "balance_sheet",
    form990: ["TotalNetAssetsFundBalanceGrp/EOYAmt", "NetAssetsOrFundBalancesEOYAmt"],
    form990ez: ["NetAssetsOrFundBalancesEOYAmt", "NetAssetsOrFundBalancesGrp/EOYAmt"]
  },
  {
    key: "cash_savings_eoy",
    label: "Cash & savings (end of year)",
    group: "balance_sheet",
    form990: ["CashNonInterestBearingGrp/EOYAmt", "SavingsAndTempCashInvstGrp/EOYAmt"],
    form990ez: ["CashSavingsAndInvestmentsGrp/EOYAmt"],
    note: "On the full 990 this sums two cash lines. The EZ line also mixes in investments, so EZ values are marked partial."
  },
  {
    key: "land_buildings_equipment_net",
    label: "Land, buildings & equipment (net)",
    group: "balance_sheet",
    form990: ["LandBldgEquipBasisNetGrp/EOYAmt"],
    form990ez: ["LandAndBuildingsGrp/EOYAmt"]
  },
  {
    key: "employee_count",
    label: "Employee count",
    group: "organization",
    form990: ["TotalEmployeeCnt"],
    form990ez: []
  }
];

export const CONCEPT_GROUP_LABELS: Record<ConceptGroup, string> = {
  revenue: "Revenue",
  expenses: "Expenses",
  balance_sheet: "Balance sheet",
  organization: "Organization"
};
