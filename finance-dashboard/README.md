# Finance Dashboard — Paso 1: Estructura y Modelo de Datos

Stack: **Next.js 14 (App Router) + TypeScript + Tailwind CSS + Prisma + PostgreSQL**,
shadcn/ui para componentes, Recharts para gráficos.

## Estructura de carpetas

```
finance-dashboard/
├── prisma/
│   ├── schema.prisma          # Modelo de datos (fuente de verdad)
│   └── seed.ts                # (Paso 2) datos de ejemplo
├── src/
│   ├── app/
│   │   ├── layout.tsx                # (Paso 3) shell, dark mode por defecto
│   │   ├── globals.css               # (Paso 3) tema, tokens de color
│   │   ├── page.tsx                  # (Paso 3) Dashboard principal
│   │   ├── (dashboard)/
│   │   │   ├── transactions/         # listado + carga rápida
│   │   │   ├── budget/               # detalle 50/30/20
│   │   │   ├── liquidity/            # Pesos Transaccionales / FCI
│   │   │   ├── income/               # ingresos fijos vs variables/escalables
│   │   │   ├── investments/          # tickers, P&L
│   │   │   └── settings/             # tipo de cambio, umbrales de alerta
│   │   └── api/
│   │       ├── transactions/route.ts
│   │       ├── accounts/route.ts
│   │       ├── exchange-rate/route.ts
│   │       ├── income-sources/route.ts
│   │       ├── assets/route.ts
│   │       ├── budget/route.ts
│   │       └── net-worth/route.ts
│   ├── components/
│   │   ├── ui/                # primitivas shadcn (Button, Card, Dialog...)
│   │   ├── dashboard/         # NetWorthCard, BudgetDonutChart, IncomeExpenseBarChart
│   │   ├── forms/             # QuickTransactionForm (fricción cero)
│   │   └── layout/            # Sidebar, Topbar
│   ├── lib/
│   │   ├── db.ts                      # Prisma client singleton
│   │   ├── currency.ts                # conversión ARS <-> USD vía ExchangeRate
│   │   ├── budget-rules.ts            # lógica 50/30/20 y alertas
│   │   └── calculations/
│   │       ├── net-worth.ts
│   │       ├── emergency-fund.ts      # meses de supervivencia
│   │       └── pnl.ts                 # P&L de Asset
│   ├── types/
│   │   └── finance.ts         # tipos TS + ejemplos de payload JSON
│   ├── hooks/                  # useAccounts, useTransactions, etc. (Paso 2/3)
│   └── store/                  # estado global (zustand) (Paso 2/3)
├── public/
└── tests/
```

## Decisiones de modelado (por qué el schema es así)

1. **Montos en unidades menores (Int)**: todo se guarda como centavos/centésimos
   para no acumular error de punto flotante en sumas de miles de transacciones.

2. **Bimonetario nativo, no "USD como campo calculado"**: cada `Account` y cada
   `Transaction` tiene su propia `currency`. El patrimonio neto total en ARS o
   en USD se calcula on-demand aplicando el `ExchangeRate` más reciente del tipo
   que el usuario elija (MEP/CCL/Oficial/Blue) — así el usuario puede comparar
   "mi patrimonio en dólares MEP" vs "dólares CCL" sin re-modelar nada.

3. **Liquidez (FCI / money market)**: en vez de crear una entidad separada,
   `Account.type = MONEY_MARKET` más dos campos cacheados
   (`cachedPrincipal`, `cachedYield`) resuelven el pedido de "separar capital
   inmovilizado del capital que genera rendimiento". El rendimiento diario se
   registra como `Transaction.type = YIELD` (ver `EXAMPLE_MONEY_MARKET_YIELD_PAYLOAD`
   en `finance.ts`), lo que además te da el historial de interés devengado día
   por día sin tocar el capital.

4. **50/30/20 vive en la transacción, no en una tabla aparte**: cada `EXPENSE`
   (y opcionalmente los `TRANSFER` hacia cuentas de ahorro/inversión) lleva un
   `budgetCategory`. Los porcentajes objetivo y los umbrales de alerta son
   configurables por usuario en `BudgetSettings` (no hardcodeados en 50/30/20,
   por si alguien quiere ajustar su regla).

5. **Ingresos**: `IncomeSource` separa el *catálogo* de fuentes (con su
   `scalability: LINEAR | SCALABLE`) de las `Transaction.type = INCOME`
   individuales. Esto permite responder directamente "¿qué % de mi ingreso
   total vino de fuentes escalables este mes?" agrupando transacciones por
   `incomeSource.scalability`.

6. **Fondo de emergencia**: no es un balance fijo, es una fórmula —
   `EmergencyFund.targetMonths` + una tabla puente `EmergencyFundAccount`
   (puede estar repartido en varias cuentas líquidas) + el gasto mensual
   promedio real (o un override manual). "Meses de supervivencia" se calcula
   en `lib/calculations/emergency-fund.ts` en el Paso 2.

7. **Activos financieros**: `Asset` guarda cantidad + costo promedio de
   compra (no lotes individuales, para mantenerlo simple en esta iteración).
   El precio de mercado se cachea (`lastPrice`) pero se refresca desde una
   API externa en el Paso 2; el P&L es `(lastPrice - avgCostPerUnit) * quantity`.

8. **`NetWorthSnapshot`** queda modelado para una fase futura (tendencia de
   patrimonio neto en el tiempo), no es parte del MVP de Step 2/3 pero no
   quería que faltara en el esquema si después se pide ese gráfico.

## Qué falta para Paso 2 (backend/lógica de estado)

- `lib/db.ts`, `lib/currency.ts`, `lib/budget-rules.ts`, `lib/calculations/*`
- Rutas API (`src/app/api/**/route.ts`)
- `prisma/seed.ts` con datos de ejemplo
- Integración con una fuente de tipo de cambio (MEP/CCL) — a definir si es
  manual, scraping o alguna API pública

## Qué falta para Paso 3 (UI)

- `app/layout.tsx` + dark mode + tokens de color
- Dashboard principal (Patrimonio Neto, dona 50/30/20, barras Ingresos vs Gastos)
- `QuickTransactionForm` de fricción cero
