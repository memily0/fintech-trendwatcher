"""Built-in demo dataset for the hackathon prototype.

The dataset intentionally mixes useful fintech signals, reposts, duplicate
headlines, and obvious noise. This makes the demo deterministic and keeps the
prototype independent from network availability.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


BASE_DATE = date(2026, 5, 12)


SIGNALS: list[dict[str, Any]] = [
    {
        "topic": "stripe_tap_to_pay",
        "title": "Stripe expands Tap to Pay for small merchants across Europe",
        "category": "payments",
        "companies": "Stripe",
        "snippet": (
            "Stripe is expanding Tap to Pay support for small merchants in several European "
            "markets, positioning phones as card acceptance terminals without extra hardware."
        ),
        "sources": [
            ("Finextra", "https://www.finextra.com/newsarticle/stripe-tap-to-pay-europe?utm_source=newsletter"),
            ("The Paypers", "https://thepaypers.com/mobile-payments/stripe-expands-tap-to-pay-in-europe"),
            ("PYMNTS", "https://www.pymnts.com/stripe-tap-to-pay-europe-rollout"),
        ],
        "duplicates": [
            "Stripe rolls out Tap to Pay expansion for European SMEs",
            "Stripe Tap to Pay reaches more merchants in Europe",
        ],
    },
    {
        "topic": "digital_euro_wallet",
        "title": "ECB publishes new digital euro wallet prototype findings",
        "category": "regulation",
        "companies": "ECB",
        "snippet": (
            "The European Central Bank shared findings from digital euro wallet prototype "
            "work, including offline payments, privacy controls and commercial bank roles."
        ),
        "sources": [
            ("ECB", "https://www.ecb.europa.eu/paym/digital_euro/prototype-findings"),
            ("Finextra", "https://www.finextra.com/newsarticle/ecb-digital-euro-wallet-prototype"),
        ],
        "duplicates": ["ECB updates banks on digital euro wallet prototype"],
    },
    {
        "topic": "visa_passkeys",
        "title": "Visa launches passkey-based checkout pilot for bank cards",
        "category": "fraud_risk",
        "companies": "Visa",
        "snippet": (
            "Visa announced a passkey checkout pilot designed to reduce card-not-present "
            "fraud and simplify authentication for issuers and merchants."
        ),
        "sources": [
            ("Visa", "https://usa.visa.com/about-visa/newsroom/press-releases/passkey-checkout-pilot.html"),
            ("PYMNTS", "https://www.pymnts.com/visa-passkey-checkout-pilot"),
        ],
        "duplicates": ["Visa pilots passkeys for card checkout authentication"],
    },
    {
        "topic": "revolut_business_lending",
        "title": "Revolut adds working capital loans for business banking customers",
        "category": "banking_product",
        "companies": "Revolut",
        "snippet": (
            "Revolut is introducing working capital loans for business accounts, using "
            "account activity and cash-flow data to pre-qualify small companies."
        ),
        "sources": [
            ("TechCrunch", "https://techcrunch.com/2026/05/08/revolut-working-capital-loans"),
            ("Finextra", "https://www.finextra.com/newsarticle/revolut-business-working-capital"),
        ],
        "duplicates": ["Revolut targets SMEs with cash-flow based business loans"],
    },
    {
        "topic": "open_banking_payments",
        "title": "UK banks test variable recurring payments for subscription commerce",
        "category": "payments",
        "companies": "Open Banking Limited",
        "snippet": (
            "A group of UK banks and payment providers started testing variable recurring "
            "payments for subscriptions and bill pay, expanding open banking beyond account access."
        ),
        "sources": [
            ("Open Banking UK", "https://www.openbanking.org.uk/news/variable-recurring-payments-pilot"),
            ("The Paypers", "https://thepaypers.com/online-payments/uk-vrp-subscription-commerce"),
        ],
        "duplicates": ["UK open banking pilots VRP for recurring commerce"],
    },
    {
        "topic": "bnpl_regulation",
        "title": "Consumer regulator proposes stricter disclosures for BNPL providers",
        "category": "regulation",
        "companies": "CFPB",
        "snippet": (
            "A consumer regulator proposed clearer disclosures and complaint handling rules "
            "for buy-now-pay-later providers, bringing BNPL closer to card-like oversight."
        ),
        "sources": [
            ("CFPB", "https://www.consumerfinance.gov/about-us/newsroom/bnpl-disclosure-rules"),
            ("Finextra", "https://www.finextra.com/newsarticle/regulator-bnpl-disclosure-rules"),
        ],
        "duplicates": ["Regulator moves to tighten BNPL disclosure requirements"],
    },
    {
        "topic": "jpmorgan_biometrics",
        "title": "JPMorgan pilots palm biometric payments with stadium merchants",
        "category": "UX",
        "companies": "JPMorgan",
        "snippet": (
            "JPMorgan is piloting palm biometric payments at stadium merchants, combining "
            "identity, wallet enrollment and loyalty offers in one checkout flow."
        ),
        "sources": [
            ("JPMorgan", "https://www.jpmorgan.com/payments/news/palm-biometric-stadium-pilot"),
            ("PYMNTS", "https://www.pymnts.com/biometrics/jpmorgan-palm-payments-stadium"),
        ],
        "duplicates": ["JPMorgan tests palm payments for stadium checkout"],
    },
    {
        "topic": "embedded_insurance",
        "title": "PayPal partners with insurer to add embedded purchase protection offers",
        "category": "partnership",
        "companies": "PayPal",
        "snippet": (
            "PayPal announced an embedded insurance partnership that lets shoppers add "
            "purchase protection offers inside checkout and post-purchase account flows."
        ),
        "sources": [
            ("PayPal", "https://newsroom.paypal-corp.com/embedded-insurance-purchase-protection"),
            ("The Paypers", "https://thepaypers.com/online-payments/paypal-embedded-insurance-checkout"),
        ],
        "duplicates": ["PayPal adds embedded protection offers through insurance partner"],
    },
    {
        "topic": "tokenized_deposits",
        "title": "BIS project tests tokenized deposits for cross-border settlement",
        "category": "market_signal",
        "companies": "BIS",
        "snippet": (
            "A BIS innovation project tested tokenized deposits for cross-border settlement, "
            "focusing on interoperability between commercial bank money and central bank money."
        ),
        "sources": [
            ("BIS", "https://www.bis.org/about/bisih/tokenized-deposits-cross-border-settlement.htm"),
            ("Finextra", "https://www.finextra.com/newsarticle/bis-tokenized-deposits-cross-border"),
        ],
        "duplicates": ["BIS tests tokenized commercial bank deposits for settlement"],
    },
    {
        "topic": "ai_fraud_detection",
        "title": "Mastercard launches AI service for real-time mule account detection",
        "category": "fraud_risk",
        "companies": "Mastercard",
        "snippet": (
            "Mastercard launched an AI service that helps banks detect mule accounts and "
            "suspicious payment flows before funds leave the banking network."
        ),
        "sources": [
            ("Mastercard", "https://www.mastercard.com/news/press/ai-mule-account-detection"),
            ("Finextra", "https://www.finextra.com/newsarticle/mastercard-ai-mule-account-detection"),
        ],
        "duplicates": ["Mastercard uses AI to help banks detect mule accounts"],
    },
    {
        "topic": "klarna_bank_account",
        "title": "Klarna expands savings account and debit features in Europe",
        "category": "banking_product",
        "companies": "Klarna",
        "snippet": (
            "Klarna expanded savings account and debit features in Europe, deepening its "
            "move from checkout financing into everyday banking relationships."
        ),
        "sources": [
            ("TechCrunch", "https://techcrunch.com/2026/05/06/klarna-savings-debit-europe"),
            ("Finextra", "https://www.finextra.com/newsarticle/klarna-savings-debit-europe"),
        ],
        "duplicates": ["Klarna pushes further into everyday banking with savings features"],
    },
    {
        "topic": "central_bank_ai_guidance",
        "title": "Central bank publishes guidance on AI model risk in financial services",
        "category": "regulation",
        "companies": "Bank of England",
        "snippet": (
            "A central bank published guidance on AI model risk management for financial "
            "services, calling for governance, monitoring and explainability controls."
        ),
        "sources": [
            ("Bank of England", "https://www.bankofengland.co.uk/prudential-regulation/ai-model-risk-guidance"),
            ("Finextra", "https://www.finextra.com/newsarticle/central-bank-ai-model-risk-guidance"),
        ],
        "duplicates": ["Banking regulator issues AI model risk guidance"],
    },
]


NOISE: list[dict[str, str]] = [
    {
        "title": "Top 10 cryptocurrency coins to watch this weekend",
        "source": "CryptoDaily",
        "url": "https://cryptodaily.example/top-10-coins-weekend?utm_campaign=seo",
        "snippet": "A speculative list of crypto tokens based on short-term price momentum and social media buzz.",
    },
    {
        "title": "Senior backend engineer vacancy at fast-growing payments startup",
        "source": "JobsBoard",
        "url": "https://jobs.example/payments-backend-engineer",
        "snippet": "A vacancy for a backend engineer with Python and Kubernetes experience.",
    },
    {
        "title": "Sponsored: five ways to improve your payment landing page",
        "source": "MarketingWire",
        "url": "https://marketingwire.example/sponsored-payment-landing-page",
        "snippet": "Sponsored content about generic landing page conversion tactics for online merchants.",
    },
    {
        "title": "Bank shares rise after analyst upgrades earnings outlook",
        "source": "MarketWatch",
        "url": "https://marketwatch.example/bank-shares-earnings-upgrade",
        "snippet": "Banking stocks rose after an analyst increased earnings forecasts for the sector.",
    },
    {
        "title": "Online course: learn fintech product management in six weeks",
        "source": "EduPromo",
        "url": "https://education.example/fintech-product-course",
        "snippet": "A promotional course landing page with early bird pricing and testimonials.",
    },
    {
        "title": "Bitcoin price prediction: traders expect another volatile week",
        "source": "CoinPriceNow",
        "url": "https://coinprice.example/bitcoin-price-prediction-week",
        "snippet": "Short-term price speculation based on chart patterns, leverage data and influencer posts.",
    },
    {
        "title": "Generic press release distribution package for financial companies",
        "source": "PRBoost",
        "url": "https://prboost.example/finance-press-release-package",
        "snippet": "A sales page offering discounted press release distribution packages to financial brands.",
    },
    {
        "title": "Weekly stock market recap: banks mixed as rates remain uncertain",
        "source": "TradingDesk",
        "url": "https://tradingdesk.example/weekly-bank-stock-market-recap",
        "snippet": "Market recap focused on share prices, rates, indexes and analyst calls rather than product signals.",
    },
]


FILLER: list[dict[str, str]] = [
    {
        "title": "Neobank adds family budgeting spaces to mobile app",
        "source": "Finextra",
        "url": "https://www.finextra.com/newsarticle/neobank-family-budgeting-spaces",
        "category": "UX",
        "snippet": "A neobank added shared budgeting spaces and spending controls for families inside its mobile app.",
    },
    {
        "title": "Payments startup launches instant refunds API for marketplaces",
        "source": "The Paypers",
        "url": "https://thepaypers.com/online-payments/instant-refunds-api-marketplaces",
        "category": "payments",
        "snippet": "A payments startup launched an API that lets marketplaces issue instant refunds to cards and wallets.",
    },
    {
        "title": "Bank rolls out carbon insights for SME transaction accounts",
        "source": "Finextra",
        "url": "https://www.finextra.com/newsarticle/bank-carbon-insights-sme-accounts",
        "category": "banking_product",
        "snippet": "A bank added carbon insight estimates to SME account dashboards and supplier analytics.",
    },
    {
        "title": "Fraud network data-sharing pilot expands to more banks",
        "source": "PYMNTS",
        "url": "https://www.pymnts.com/fraud-data-sharing-pilot-banks",
        "category": "fraud_risk",
        "snippet": "A fraud intelligence pilot expanded to additional banks to improve detection of mule networks.",
    },
    {
        "title": "Regulator opens consultation on open finance consent dashboards",
        "source": "Regulator",
        "url": "https://regulator.example/open-finance-consent-dashboard-consultation",
        "category": "regulation",
        "snippet": "A regulator opened a consultation on consumer consent dashboards for open finance data sharing.",
    },
    {
        "title": "Card network tests merchant-funded loyalty inside banking apps",
        "source": "Visa",
        "url": "https://usa.visa.com/about-visa/newsroom/merchant-funded-loyalty-banking-apps.html",
        "category": "partnership",
        "snippet": "A card network is testing merchant-funded offers delivered through issuer banking apps.",
    },
]


def demo_articles() -> list[dict[str, str]]:
    """Return a deterministic article list with useful signals and noise."""

    rows: list[dict[str, str]] = []
    idx = 1
    for signal_idx, signal in enumerate(SIGNALS):
        for source_idx, (source, url) in enumerate(signal["sources"]):
            title = signal["title"]
            if source_idx > 0 and signal.get("duplicates"):
                title = signal["duplicates"][(source_idx - 1) % len(signal["duplicates"])]
            rows.append(
                {
                    "id": f"a{idx:03d}",
                    "title": title,
                    "url": url,
                    "source": source,
                    "published_at": str(BASE_DATE - timedelta(days=(signal_idx + source_idx) % 12)),
                    "snippet": signal["snippet"],
                    "text": (
                        f"{signal['snippet']} The publication mentions {signal['companies']} and "
                        f"connects the update with {signal['category']} use cases for banks."
                    ),
                }
            )
            idx += 1

        # Add one low-quality repost for selected signals to make dedup visible.
        if signal_idx % 2 == 0:
            rows.append(
                {
                    "id": f"a{idx:03d}",
                    "title": signal["duplicates"][0] if signal.get("duplicates") else signal["title"],
                    "url": f"https://fintechrepost.example/{signal['topic']}?utm_source=telegram",
                    "source": "Fintech Repost",
                    "published_at": str(BASE_DATE - timedelta(days=(signal_idx + 2) % 12)),
                    "snippet": signal["snippet"] + " The article republishes details from another industry source.",
                    "text": signal["snippet"],
                }
            )
            idx += 1

    for noise_idx, noise in enumerate(NOISE):
        rows.append(
            {
                "id": f"a{idx:03d}",
                "title": noise["title"],
                "url": noise["url"],
                "source": noise["source"],
                "published_at": str(BASE_DATE - timedelta(days=noise_idx % 9)),
                "snippet": noise["snippet"],
                "text": noise["snippet"],
            }
        )
        idx += 1

    for filler_idx, item in enumerate(FILLER):
        rows.append(
            {
                "id": f"a{idx:03d}",
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "published_at": str(BASE_DATE - timedelta(days=(filler_idx + 3) % 14)),
                "snippet": item["snippet"],
                "text": item["snippet"] + f" This update is relevant to {item['category']} teams.",
            }
        )
        idx += 1

    # A few exact URL duplicates with tracking params.
    for copy_idx, original in enumerate(rows[:6]):
        duplicated = dict(original)
        duplicated["id"] = f"a{idx:03d}"
        duplicated["url"] = original["url"] + ("&utm_medium=social" if "?" in original["url"] else "?utm_medium=social")
        duplicated["source"] = original["source"]
        duplicated["published_at"] = str(BASE_DATE - timedelta(days=(copy_idx + 1) % 7))
        rows.append(duplicated)
        idx += 1

    return rows
