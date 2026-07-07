import { LegalPage } from "@/components/legal/legal-page";

// TEMPLATE — requires review by qualified legal counsel before public launch.
export const metadata = { title: "Risk Disclosure — Forge Terminal" };

export default function DisclaimerPage() {
  return (
    <LegalPage
      title="Risk Disclosure"
      updated="July 2026"
      sections={[
        {
          heading: "Trading digital assets is extremely risky",
          body: [
            "Tokens surfaced by Forge Terminal — particularly newly launched tokens on Solana — are highly speculative and can lose all of their value within minutes. You should never trade with funds you cannot afford to lose entirely.",
            "Scores shown in the terminal (rug risk, momentum, sustainability, and similar) are automated heuristics computed from on-chain data. They are informational signals, not investment advice, and they can be wrong. A low rug-risk score is not a guarantee that a token is safe.",
          ],
        },
        {
          heading: "Nothing here is financial advice",
          body: [
            "Forge Terminal is an information and execution tool. Nothing displayed in the product — including wallet leaderboards, shadow ledgers, quotes, and copy suggestions — constitutes financial, investment, legal, or tax advice, or a recommendation to buy or sell any asset.",
            "Copy-trading features show what another wallet did. Past performance of any wallet does not predict future results, and leaderboard wallets have no relationship with, or duty to, you.",
          ],
        },
        {
          heading: "You control your keys and your transactions",
          body: [
            "Forge Terminal is non-custodial: we never hold your funds or private keys. Every transaction is built for your review and signed in your own wallet. You are solely responsible for verifying each transaction — including amounts, tokens, and slippage — before signing.",
            "Blockchain transactions are irreversible. Neither Forge Terminal nor anyone else can reverse, refund, or recover a transaction you sign.",
          ],
        },
        {
          heading: "Data and availability",
          body: [
            "Prices, quotes, and on-chain metrics come from third-party sources (including Jupiter and Solana RPC providers) and may be delayed, incomplete, or unavailable. The free tier intentionally delays signals. Outages, congestion, and MEV can cause executed prices to differ from quotes.",
          ],
        },
        {
          heading: "Jurisdiction",
          body: [
            "You are responsible for ensuring that your use of Forge Terminal is lawful where you live. The product is not offered to persons in jurisdictions where its use would be unlawful.",
          ],
        },
      ]}
    />
  );
}
