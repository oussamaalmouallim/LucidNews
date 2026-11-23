"""Sectors: what a LucidNews installation watches (lot 47).

A sector is a whole pack: its categories (with labels and the one-line scope the AI reads),
and, as sectors are added, its editorial profile, its source catalog and its authorities. One
sector per installation, chosen by the administrator (``Config.sector``, Settings screen).

Category IDs are unique across all sectors. So an item keeps valid categories whatever the
current sector (the archive outlives a change of sector), while what is *shown* and *asked of
the AI* is the current sector's list only.

``tech`` is the original LucidNews taxonomy (``taxonomy.Category``) and stays the default.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .taxonomy import _ALIASES, CATEGORY_LABELS, CATEGORY_SCOPES, Category

DEFAULT_SECTOR = "tech"

# The rule every sector outside tech adds to what the AI is told (finance, law and health are
# regulated trades: a news watch reports, it never advises).
NO_ADVICE_RULE = (
    "Report what the source says; never give advice. Do not recommend buying, selling or holding "
    "anything, do not tell a reader what to do legally or medically, and do not turn a forecast, "
    "an opinion or a draft into a fact. A figure, a date or a decision appears only if the source gives it."
)


@dataclass(frozen=True)
class SectorCategory:
    id: str
    labels: Dict[str, str]
    scope: str  # one line, in English: what the AI files under this category
    aliases: Tuple[str, ...] = ()

    def label(self, language: str) -> str:
        return self.labels.get(language, self.labels["en"])


@dataclass(frozen=True)
class Sector:
    id: str
    labels: Dict[str, str]
    descriptions: Dict[str, str]
    categories: Tuple[SectorCategory, ...]
    # Rules added to every prompt of this sector (analysis and writing). Empty for tech, whose
    # prompts stay exactly as they were.
    rules: Tuple[str, ...] = ()
    # The sector in a sentence ("tech" in « la veille tech », "tech news"), lower case.
    nouns: Dict[str, str] = field(default_factory=dict)

    def rules_text(self) -> str:
        return "\n".join(f"- {rule}" for rule in self.rules)

    @property
    def category_ids(self) -> List[str]:
        return [category.id for category in self.categories]

    def label(self, language: str) -> str:
        return self.labels.get(language, self.labels["en"])

    def payload(self) -> Dict[str, object]:
        """What the web app needs: names and categories, never more."""
        return {
            "id": self.id,
            "labels": dict(self.labels),
            "descriptions": dict(self.descriptions),
            "nouns": dict(self.nouns),
            "categories": [{"id": category.id, "labels": dict(category.labels)} for category in self.categories],
        }


def _tech() -> Sector:
    aliases: Dict[Category, List[str]] = {}
    for alias, category in _ALIASES.items():
        aliases.setdefault(category, []).append(alias)
    return Sector(
        id="tech",
        labels={"en": "Technology & IT", "fr": "Tech et IT"},
        nouns={"en": "tech", "fr": "tech"},
        descriptions={
            "en": "AI, software, cloud, security, data and the rest of IT.",
            "fr": "IA, logiciel, cloud, sécurité, data et le reste de l'IT.",
        },
        categories=tuple(
            SectorCategory(category.value, dict(CATEGORY_LABELS[category]), CATEGORY_SCOPES[category], tuple(aliases.get(category, ())))
            for category in Category
        ),
    )


def _finance() -> Sector:
    """Finance (phase 2): markets, banks, insurance, crypto-assets, deals, the economy, the
    rules of finance and fintech. A news watch for people who follow money, never an adviser."""
    return Sector(
        id="finance",
        labels={"en": "Finance", "fr": "Finance"},
        nouns={"en": "finance", "fr": "finance"},
        descriptions={
            "en": "Markets, banks, insurance, crypto-assets, deals, the economy and financial regulation.",
            "fr": "Marchés, banques, assurance, crypto-actifs, fusions, économie et régulation financière.",
        },
        categories=(
            SectorCategory(
                "finance-markets",
                {"en": "Markets", "fr": "Marchés"},
                "stock, bond, currency and commodity markets, indices, listings and trading venues",
                ("markets", "stock-market", "bourse", "equities", "bonds", "forex"),
            ),
            SectorCategory(
                "finance-banking",
                {"en": "Banking", "fr": "Banques"},
                "banks, lending, deposits, payments by banks, bank results and bank supervision",
                ("banking", "banks", "banque", "banques"),
            ),
            SectorCategory(
                "finance-insurance",
                {"en": "Insurance", "fr": "Assurance"},
                "insurers, reinsurance, pensions and asset managers' insurance products",
                ("insurance", "assurance", "assurances", "pensions"),
            ),
            SectorCategory(
                "finance-crypto",
                {"en": "Crypto-assets", "fr": "Crypto-actifs"},
                "crypto-assets, stablecoins, central bank digital currencies and their platforms",
                ("crypto", "cryptocurrency", "cryptocurrencies", "bitcoin", "stablecoins", "crypto-actifs"),
            ),
            SectorCategory(
                "finance-deals",
                {"en": "Mergers & acquisitions", "fr": "Fusions et acquisitions"},
                "mergers, acquisitions, IPOs, private equity and venture funding rounds",
                ("m&a", "mergers", "acquisitions", "ipo", "private-equity", "fusions"),
            ),
            SectorCategory(
                "finance-macro",
                {"en": "Economy", "fr": "Économie"},
                "inflation, growth, jobs, interest rates, central bank policy and public finances",
                ("macro", "macroeconomics", "economy", "economie", "monetary-policy", "central-banks"),
            ),
            SectorCategory(
                "finance-regulation",
                {"en": "Financial regulation", "fr": "Régulation financière"},
                "financial rules, supervisors' decisions, sanctions, enforcement and compliance",
                ("financial-regulation", "regulation", "compliance", "enforcement", "regulateurs"),
            ),
            SectorCategory(
                "finance-fintech",
                {"en": "Fintech", "fr": "Fintech"},
                "fintech companies, digital payments, neobanks and financial technology",
                ("fintech", "payments", "neobanks", "paiements"),
            ),
        ),
        rules=(NO_ADVICE_RULE,),
    )


def _legal() -> Sector:
    """Legal and regulatory (phase 3): new texts, court decisions and the authorities that apply
    them. A watch that tells what a text or a decision says, never legal advice."""
    return Sector(
        id="legal",
        labels={"en": "Legal & regulatory", "fr": "Juridique et réglementaire"},
        nouns={"en": "legal", "fr": "juridique"},
        descriptions={
            "en": "Legislation, case law, business and employment law, data protection, EU law and compliance.",
            "fr": "Législation, jurisprudence, droit des affaires et du travail, données personnelles, droit européen et conformité.",
        },
        categories=(
            SectorCategory(
                "legal-legislation",
                {"en": "Legislation", "fr": "Législation"},
                "laws, decrees, orders and bills: adopted, published, debated or entering into force",
                ("legislation", "législation", "lois", "law-making", "decrees", "décrets"),
            ),
            SectorCategory(
                "legal-case-law",
                {"en": "Case law", "fr": "Jurisprudence"},
                "decisions of courts and constitutional councils that settle or change how the law applies",
                ("case-law", "jurisprudence", "court-decisions", "courts", "rulings"),
            ),
            SectorCategory(
                "legal-business",
                {"en": "Business law", "fr": "Droit des affaires"},
                "company, contract, competition, insolvency and tax law affecting businesses",
                ("business-law", "droit-des-affaires", "corporate-law", "competition-law", "concurrence"),
            ),
            SectorCategory(
                "legal-employment",
                {"en": "Employment law", "fr": "Droit du travail"},
                "employment contracts, working time, dismissal, social security and labour relations law",
                ("employment-law", "labour-law", "droit-du-travail", "droit-social"),
            ),
            SectorCategory(
                "legal-data-protection",
                {"en": "Data protection", "fr": "Données personnelles"},
                "privacy and personal data law, GDPR, data protection authorities' decisions and fines",
                ("data-protection", "privacy", "gdpr", "rgpd", "données-personnelles", "cnil"),
            ),
            SectorCategory(
                "legal-eu",
                {"en": "EU law", "fr": "Droit européen"},
                "EU regulations and directives, the EU Court of Justice and European institutions' legal acts",
                ("eu-law", "droit-européen", "droit-de-l'union", "european-law", "cjeu", "cjue"),
            ),
            SectorCategory(
                "legal-compliance",
                {"en": "Compliance", "fr": "Conformité"},
                "obligations firms must meet: anti-corruption, sanctions, due diligence, sector rules and their enforcement",
                ("legal-compliance", "conformité", "conformite", "anti-corruption", "due-diligence"),
            ),
            SectorCategory(
                "legal-public",
                {"en": "Public law", "fr": "Droit public"},
                "administrative law, public procurement, local authorities, fundamental rights and the Council of State",
                ("public-law", "droit-public", "administrative-law", "droit-administratif", "marchés-publics"),
            ),
        ),
        rules=(NO_ADVICE_RULE,),
    )


def _health() -> Sector:
    """Health and pharma (phase 4): authorities' decisions, medicines, trials, devices, public
    health, digital health, biotech and care providers. A cautious watch: a promise is never a fact,
    and it never gives medical advice."""
    return Sector(
        id="health",
        labels={"en": "Health & pharma", "fr": "Santé et pharma"},
        nouns={"en": "health", "fr": "santé"},
        descriptions={
            "en": "Health regulation, medicines, clinical trials, medical devices, public health, digital health and biotech.",
            "fr": "Réglementation, médicaments, essais cliniques, dispositifs médicaux, santé publique, e-santé et biotechnologies.",
        },
        categories=(
            SectorCategory(
                "health-regulation",
                {"en": "Health regulation", "fr": "Réglementation santé"},
                "decisions, guidance and rules of health authorities and health ministries, pricing and reimbursement",
                ("health-regulation", "réglementation-santé", "health-policy", "reimbursement", "remboursement"),
            ),
            SectorCategory(
                "health-drugs",
                {"en": "Medicines", "fr": "Médicaments"},
                "medicines and vaccines: approvals, safety alerts, shortages, recalls and pharmaceutical companies",
                ("drugs", "medicines", "médicaments", "pharma", "pharmaceuticals", "vaccines", "vaccins"),
            ),
            SectorCategory(
                "health-trials",
                {"en": "Clinical trials", "fr": "Essais cliniques"},
                "clinical trials and medical research results, with their stage and whether they are peer reviewed",
                ("clinical-trials", "essais-cliniques", "trials", "medical-research", "recherche-médicale"),
            ),
            SectorCategory(
                "health-devices",
                {"en": "Medical devices", "fr": "Dispositifs médicaux"},
                "medical devices and diagnostics: approvals, recalls, safety notices and their makers",
                ("medical-devices", "dispositifs-médicaux", "medtech", "diagnostics"),
            ),
            SectorCategory(
                "health-public",
                {"en": "Public health", "fr": "Santé publique"},
                "epidemics, surveillance, prevention campaigns and population health data",
                ("public-health", "santé-publique", "epidemics", "épidémies", "epidemiology", "épidémiologie"),
            ),
            SectorCategory(
                "health-digital",
                {"en": "Digital health", "fr": "E-santé"},
                "digital health: health data, telemedicine, health apps and AI used in care",
                ("digital-health", "e-santé", "esante", "telemedicine", "télémédecine", "health-data"),
            ),
            SectorCategory(
                "health-biotech",
                {"en": "Biotech", "fr": "Biotechnologies"},
                "biotech companies, gene and cell therapies, and their funding and deals",
                ("biotech", "biotechnologies", "biotechnology", "gene-therapy", "thérapie-génique"),
            ),
            SectorCategory(
                "health-care",
                {"en": "Care providers", "fr": "Établissements de santé"},
                "hospitals, clinics, care homes and health professionals: organisation, funding and staffing",
                ("hospitals", "hôpitaux", "hopital", "care-providers", "établissements-de-santé", "ehpad"),
            ),
        ),
        rules=(NO_ADVICE_RULE,),
    )


def _energy() -> Sector:
    """Energy and climate (phase 5): energy markets, renewables, energy efficiency and white
    certificates (CEE), building renovation, grids and storage, regulation, climate and CSR, and
    mobility. Useful to energy professionals: what changes, from when, for whom."""
    return Sector(
        id="energy",
        labels={"en": "Energy & climate", "fr": "Énergie et climat"},
        nouns={"en": "energy", "fr": "énergie"},
        descriptions={
            "en": "Energy markets, renewables, energy efficiency and white certificates, renovation, grids, regulation, climate and mobility.",
            "fr": "Marchés de l'énergie, renouvelables, efficacité énergétique et CEE, rénovation, réseaux, réglementation, climat et mobilité.",
        },
        categories=(
            SectorCategory(
                "energy-markets",
                {"en": "Energy markets", "fr": "Marchés de l'énergie"},
                "prices and supply of electricity, gas, oil and nuclear power, energy companies and their results",
                ("energy-markets", "marchés-de-l'énergie", "energy-prices", "prix-de-l'énergie", "oil", "pétrole", "gas", "gaz", "nuclear", "nucléaire"),
            ),
            SectorCategory(
                "energy-renewables",
                {"en": "Renewables", "fr": "Renouvelables"},
                "solar, wind, hydro, biomass, biogas and hydrogen: projects, tenders, capacity and their makers",
                ("renewables", "renouvelables", "énergies-renouvelables", "solar", "solaire", "wind", "éolien", "hydrogen", "hydrogène", "biogas", "biogaz"),
            ),
            SectorCategory(
                "energy-efficiency",
                {"en": "Energy efficiency & white certificates", "fr": "Efficacité énergétique et CEE"},
                "energy savings in industry, buildings and services, and the white certificate scheme (CEE in France): standardised operations, obligations, prices and checks",
                ("energy-efficiency", "efficacité-énergétique", "cee", "white-certificates", "certificats-d'économies-d'énergie", "économies-d'énergie"),
            ),
            SectorCategory(
                "energy-renovation",
                {"en": "Building renovation", "fr": "Rénovation"},
                "energy renovation of homes and buildings: subsidies, energy performance ratings, heat pumps, insulation and certified installers",
                ("renovation", "rénovation", "rénovation-énergétique", "building-renovation", "maprimerénov", "dpe", "rge", "heat-pumps", "pompes-à-chaleur"),
            ),
            SectorCategory(
                "energy-grids",
                {"en": "Grids & storage", "fr": "Réseaux et stockage"},
                "electricity and gas networks, interconnections, storage, batteries and the balance of supply and demand",
                ("grids", "réseaux", "réseaux-électriques", "power-grid", "storage", "stockage", "batteries", "energy-storage"),
            ),
            SectorCategory(
                "energy-regulation",
                {"en": "Energy regulation", "fr": "Réglementation énergie"},
                "energy laws, decrees, orders and regulator decisions, tariffs, energy policy and planning",
                ("energy-regulation", "réglementation-énergie", "energy-policy", "politique-énergétique", "tarifs-réglementés"),
            ),
            SectorCategory(
                "energy-climate",
                {"en": "Climate & CSR", "fr": "Climat et RSE"},
                "climate policy and science, emissions and carbon markets, adaptation, corporate sustainability reporting and CSR",
                ("climate", "climat", "csr", "rse", "esg", "csrd", "emissions", "émissions", "carbon", "carbone", "climate-change"),
            ),
            SectorCategory(
                "energy-mobility",
                {"en": "Mobility", "fr": "Mobilité"},
                "electric vehicles, charging, low-carbon fuels and the energy transition of transport",
                ("mobility", "mobilité", "electric-vehicles", "véhicules-électriques", "ev", "charging", "recharge", "biofuels", "biocarburants"),
            ),
        ),
        rules=(NO_ADVICE_RULE,),
    )


SECTORS: Dict[str, Sector] = {sector.id: sector for sector in (_tech(), _finance(), _legal(), _health(), _energy())}


def get_sector(sector_id: str) -> Sector:
    """The sector, or the default one for an unknown ID (an old configuration stays readable)."""
    return SECTORS.get(sector_id, SECTORS[DEFAULT_SECTOR])


def all_categories() -> List[SectorCategory]:
    """Every category of every sector, sector by sector, in each sector's order."""
    return [category for sector in SECTORS.values() for category in sector.categories]


def _check_unique_ids() -> None:
    seen: Dict[str, str] = {}
    for sector in SECTORS.values():
        for category in sector.categories:
            if category.id in seen:
                raise ValueError(f"category {category.id} belongs to {seen[category.id]} and {sector.id}")
            seen[category.id] = sector.id


_check_unique_ids()
