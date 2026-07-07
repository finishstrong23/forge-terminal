import { LegalPage } from "@/components/legal/legal-page";

// TEMPLATE — requires review by qualified legal counsel before public launch.
export const metadata = { title: "Privacy Policy — Forge Terminal" };

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      updated="July 2026"
      sections={[
        {
          heading: "What we collect",
          body: [
            "Account data: your email address and a hash of your password (we never store the password itself). Billing data: handled by Stripe; we store only your Stripe customer reference and subscription state, never card numbers.",
            "Product data: wallets you follow, your shadow-trade ledger, and trades you choose to record. Wallet addresses you connect are used client-side to build transactions; connecting a wallet does not link it to your account unless you record a trade.",
            "Technical data: server logs (including IP addresses used for rate limiting) and error reports via Sentry.",
          ],
        },
        {
          heading: "What we don't collect",
          body: [
            "We never hold your private keys or funds, and we do not sell your personal data to anyone.",
          ],
        },
        {
          heading: "How we use data",
          body: [
            "To operate the service (authentication, tier enforcement, billing), to send transactional email (verification, password reset, and alert digests you enable), and to diagnose failures. Public on-chain data (token and wallet activity) is processed to produce the analytics the product exists to provide.",
          ],
        },
        {
          heading: "Third parties",
          body: [
            "We rely on infrastructure and data providers including Railway (hosting), Vercel (web hosting), Stripe (payments), Sentry (error reporting), Helius and other Solana RPC providers, and Jupiter (quotes). Each receives only the data needed for its function.",
          ],
        },
        {
          heading: "Retention and your choices",
          body: [
            "Account and ledger data is retained while your account exists. Contact us to delete your account and associated personal data; on-chain data is public by nature and outside our control.",
          ],
        },
      ]}
    />
  );
}
