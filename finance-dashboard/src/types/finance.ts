// ============================================================================
// Tipos TypeScript que reflejan el schema de Prisma, para uso en frontend
// (formularios, gráficos) y como contrato de la API.
// Los montos viajan en unidades menores (centavos/centésimos), igual que en DB.
// ============================================================================

export type Currency = "ARS" | "USD";

export type AccountType =
  | "CHECKING"
  | "MONEY_MARKET"
  | "BROKERAGE"
  | "CASH"
  | "CREDIT_CARD";

export type TransactionType = "INCOME" | "EXPENSE" | "TRANSFER" | "YIELD";

export type BudgetCategory = "NECESIDADES" | "ESTILO_VIDA" | "AHORRO_INVERSION";

export type IncomeType = "FIXED" | "VARIABLE";
export type IncomeScalability = "LINEAR" | "SCALABLE";

export type AssetType = "STOCK" | "ETF" | "CEDEAR";

export type ExchangeRateType = "OFICIAL" | "MEP" | "CCL" | "BLUE" | "CRYPTO";

export type RecurrenceFrequency = "NONE" | "WEEKLY" | "BIWEEKLY" | "MONTHLY" | "YEARLY";

export interface Account {
  id: string;
  name: string;
  type: AccountType;
  currency: Currency;
  cachedBalance: number; // unidades menores
  cachedPrincipal?: number | null; // solo MONEY_MARKET
  cachedYield?: number | null; // solo MONEY_MARKET
  isArchived: boolean;
}

export interface Transaction {
  id: string;
  accountId: string;
  type: TransactionType;
  amount: number; // unidades menores, siempre positivo
  currency: Currency;
  date: string; // ISO 8601
  description?: string | null;
  merchant?: string | null;
  budgetCategory?: BudgetCategory | null;
  incomeSourceId?: string | null;
  destinationAccountId?: string | null;
  isRecurring: boolean;
  recurrence: RecurrenceFrequency;
  tags: string[];
}

export interface IncomeSource {
  id: string;
  name: string;
  type: IncomeType;
  scalability: IncomeScalability;
  currency: Currency;
  expectedAmount?: number | null;
  frequency: RecurrenceFrequency;
  isActive: boolean;
}

export interface ExchangeRate {
  id: string;
  type: ExchangeRateType;
  date: string;
  value: number; // ARS por 1 USD
  source?: string | null;
}

export interface Asset {
  id: string;
  ticker: string;
  name?: string | null;
  type: AssetType;
  currency: Currency;
  quantity: number;
  avgCostPerUnit: number; // unidades menores
  lastPrice?: number | null;
  lastPriceUpdatedAt?: string | null;
}

export interface BudgetSettings {
  necesidadesPct: number;
  estiloVidaPct: number;
  ahorroInversionPct: number;
  necesidadesAlertPct: number;
  estiloVidaAlertPct: number;
  ahorroInversionAlertPct: number;
}

export interface EmergencyFund {
  targetMonths: number;
  monthlyExpenseOverride?: number | null;
  linkedAccountIds: string[];
}

// ----------------------------------------------------------------------------
// EJEMPLO: payload real de "cargar una transacción" desde el form de
// fricción cero (POST /api/transactions). Este es el JSON que pediste
// para transacciones.
// ----------------------------------------------------------------------------

export const EXAMPLE_TRANSACTION_PAYLOAD = {
  accountId: "acc_ars_checking_main",
  type: "EXPENSE",
  amount: 1550000, // $15.500,00 ARS en centavos
  currency: "ARS",
  date: "2026-09-24T14:32:00Z",
  description: "Supermercado",
  merchant: "Carrefour",
  budgetCategory: "NECESIDADES",
  isRecurring: false,
  recurrence: "NONE",
  tags: [],
} satisfies Omit<Transaction, "id">;

export const EXAMPLE_INCOME_PAYLOAD = {
  accountId: "acc_ars_checking_main",
  type: "INCOME",
  amount: 350000000, // $3.500.000,00 ARS
  currency: "ARS",
  date: "2026-09-01T09:00:00Z",
  description: "Sueldo Septiembre",
  incomeSourceId: "inc_salario_corporativo",
  isRecurring: true,
  recurrence: "MONTHLY",
  tags: [],
} satisfies Omit<Transaction, "id">;

export const EXAMPLE_MONEY_MARKET_YIELD_PAYLOAD = {
  accountId: "acc_ars_fci_moneymarket",
  type: "YIELD",
  amount: 4200, // $42,00 ARS devengados ese día
  currency: "ARS",
  date: "2026-09-24T00:05:00Z",
  description: "Rendimiento diario FCI",
  isRecurring: false,
  recurrence: "NONE",
  tags: ["auto-generado"],
} satisfies Omit<Transaction, "id">;
