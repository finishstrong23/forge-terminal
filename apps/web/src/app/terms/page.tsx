import { LegalPage } from "@/components/legal/legal-page";

// TEMPLATE — requires review by qualified legal counsel before public launch.
export const metadata = { title: "Terms of Service — Forge Terminal" };

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms of Service"
      updated="July 2026"
      sections={[
        {
          heading: "1. The service",
          body: [
            "Forge Terminal provides token discovery signals, wallet analytics, shadow copy-trading records, and non-custodial trade execution tooling for the Solana network. We provide software and information only; we are not a broker, exchange, custodian, or investment adviser.",
          ],
        },
        {
          heading: "2. Accounts",
          body: [
            "You must provide accurate registration information and keep your credentials secure. You are responsible for all activity under your account. We may suspend accounts that abuse the service, attempt to circumvent tier limits, or violate these terms.",
          ],
        },
        {
          heading: "3. Subscriptions and billing",
          body: [
            "Paid tiers are billed through Stripe on a monthly or yearly cycle and renew automatically until cancelled. You can cancel any time via the billing portal in Settings; access continues through the end of the paid period. Except where required by law, payments are non-refundable.",
          ],
        },
        {
          heading: "4. No advice; assumption of risk",
          body: [
            "All content is informational. You acknowledge the Risk Disclosure and agree that you alone decide whether and what to trade, and that you bear all losses arising from your trading decisions.",
          ],
        },
        {
          heading: "5. Non-custodial execution",
          body: [
            "Trade execution features construct transactions that you review and sign in your own wallet. We never take possession of your assets or keys, and we do not submit transactions on your behalf.",
          ],
        },
        {
          heading: "6. Acceptable use",
          body: [
            "You may not attempt to disrupt the service, scrape it at abusive rates, resell data feeds, or use the service for unlawful activity, including market manipulation.",
          ],
        },
        {
          heading: "7. Disclaimers and limitation of liability",
          body: [
            "The service is provided “as is” without warranties of any kind. To the maximum extent permitted by law, our aggregate liability for any claim relating to the service is limited to the amounts you paid us in the twelve months preceding the claim, and we are not liable for indirect, incidental, or consequential damages, or for any trading losses.",
          ],
        },
        {
          heading: "8. Changes",
          body: [
            "We may update these terms; material changes will be announced in-product or by email. Continued use after changes take effect constitutes acceptance.",
          ],
        },
      ]}
    />
  );
}
