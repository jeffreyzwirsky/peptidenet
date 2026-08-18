# ---------------------------------------------------------------------------
# COMPLIANCE REMEDIATION 2026-08-16
#
# Removed from this module: every passage that cross-sold bacteriostatic water
# alongside a compound ("whether you already hold bacteriostatic water or need
# it in the same order", the "Reconstitution supplies" sections, the
# "Do you sell bacteriostatic water?" FAQs). Bundling a lyophilised compound
# with a diluent has been used directly as evidence of intended injection, and
# editorial cross-sell is the same evidence as a bundle SKU. Bacteriostatic
# water is itself delisted from the catalogue.
#
# STILL OPEN, and larger than these strings: there is no such thing as regional
# demand for a laboratory reagent. These 25 pages explain transit times, customs
# handling and what to confirm before ordering, addressed in the second person
# to someone receiving a parcel. Several reference rural civic addresses and
# mailroom delivery. The recommendation on file is to delete all 25 pages and
# this module with them; only the constraint-4 bundling strings have been
# removed here.
# ---------------------------------------------------------------------------
"""
Regional landing-page content for the storefront network.

WHAT THESE PAGES ARE
--------------------
Each entry in ``REGIONS`` backs one landing page for a province, territory or
state. Views, URLs and templates live elsewhere — this module is content only.

ONE REGION, ONE DOMAIN
----------------------
Every entry carries an ``owner``: the single storefront that serves it. Market
alone is not enough. Filtering only by ``CA``/``US`` meant all five ``.ca``
sites served all thirteen Canadian pages and all three ``.com`` sites served all
twelve American ones — the same Alberta page live at five domains, 65 Canadian
URLs for 13 pages of content. That is precisely the cross-domain duplication the
rest of this file is written to avoid, and it is worse than the within-file
sameness the docstring below warns about, because no amount of distinct writing
fixes it.

Canada is split so each ``.ca`` storefront owns three provinces, except
peptidesalberta.ca, which owns Alberta and its city pages — the province is in
its name, so concentrating Alberta there is the one assignment that is not
arbitrary. The United States is split four states per ``.com`` storefront.

The pages exist to answer the questions a researcher in a given place actually
has before ordering: which centres we serve, what the local time zone means for
support and order cut-offs, what the climate does to a parcel in transit, how
how customs may handle an inbound shipment in that market, which currency is shown,
and how to store and check a lyophilised vial once it lands.

THE DOORWAY-PAGE RISK, AND WHY THIS FILE IS WRITTEN THE WAY IT IS
-----------------------------------------------------------------
A network of near-identical location pages — one template with the place name
swapped — is a doorway page. Search engines flag that pattern as spam, and the
penalty is not limited to the offending pages: it can pull down the whole
network of domains. Because all eight storefronts sell one shared catalogue,
this file is one of the few places where genuine per-page difference has to be
manufactured honestly.

So every region here is written from scratch. Section topics differ, section
order differs, sentence structure differs, and each page leans on something
true about that region — the Newfoundland half-hour offset, air-only freight
into Nunavut, summer heat in Arizona, the salt air on the Nova Scotia coast.
If two pages here ever start reading like each other, that is a bug worth
fixing, not a style preference.

HARD RULES BAKED INTO EVERY STRING BELOW
----------------------------------------
* Research use only. No human or veterinary use. No medical, therapeutic or
  outcome claims of any kind. No handling instructions that describe use in a
  living subject.
* Nothing invented that could be checked and found false: no named institutions,
  companies or people; no statistics, rankings or figures; no claims about the
  specific law of any province or state.
* No shipping-origin claim, ever. We do not say which country goods leave from.
* No local presence. The honest framing is "serving researchers in X".
* No testimonials, review counts or social proof of any kind.
* One shipping window only: 10 to 15 days, stated as a window and never as a
  promise of a specific date.

Regulatory mentions stay at the level that is general and true: customs may
inspect an inbound parcel, and the buyer is responsible for meeting the rules
that apply where they are.
"""

REGIONS = [
    # ------------------------------------------------------------------
    # CANADA — 13 provinces and territories, served by the .ca storefronts
    # ------------------------------------------------------------------
    {
        "slug": "alberta",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "name": "Alberta",
        "short": "AB",
        "cities": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Grande Prairie"],
        "timezone": "Mountain Time",
        "title": "Research Peptides in Alberta | Research Use Only",
        "meta_description": (
            "Serving research buyers across Alberta. 18 lyophilised compounds, "
            "priced in Canadian dollars, 10 to 15 day shipping window. Research "
            "use only."
        ),
        "h1": "Research Peptides for Alberta",
        "intro": (
            "Alberta's research buyers are concentrated in two large metro areas "
            "with a long chain of smaller centres between and beyond them. We "
            "serve researchers across the province from the same shared "
            "catalogue that every site in our network draws on. Everything "
            "listed is supplied for laboratory research use only, and not for "
            "human or veterinary use."
        ),
        "sections": [
            {
                "h2": "Centres we cover",
                "body": (
                    "The Calgary and Edmonton metro areas account for most "
                    "Alberta orders, with Red Deer sitting roughly halfway "
                    "between them on the corridor. We also deliver to "
                    "Lethbridge and Medicine Hat in the south and to Grande "
                    "Prairie and Fort McMurray in the north. Alberta's research "
                    "base leans toward energy and agricultural science, so a "
                    "fair share of orders go to industrial park addresses "
                    "rather than downtown ones. Either works."
                ),
            },
            {
                "h2": "Mountain Time and order cut-offs",
                "body": (
                    "Alberta runs on Mountain Time. Our order queue is "
                    "processed on a fixed daily cycle, so an order placed in "
                    "the Alberta morning is picked up in that day's batch and "
                    "one placed late in the evening rolls into the following "
                    "cycle. Support replies are written to the same schedule. "
                    "If you need a message read before a batch closes, send it "
                    "earlier in the working day rather than after hours."
                ),
            },
            {
                "h2": "Winter transit and what to do when a vial lands cold",
                "body": (
                    "Alberta winters are long, and a parcel can sit at an "
                    "unheated depot or on a porch for hours. Lyophilised "
                    "material is comparatively stable in transit, and cold is "
                    "far less of a problem for it than sustained heat. When a "
                    "cold parcel arrives, let the sealed vial come up to room "
                    "temperature before you open it. That reduces condensation "
                    "on the stopper. After that, store it as the label states."
                ),
            },
            {
                "h2": "Customs and the 10 to 15 day window",
                "body": (
                    "Orders move on a 10 to 15 day window. Inbound parcels may "
                    "be subject to inspection by the Canada Border Services "
                    "Agency, and an inspection can add days that are outside "
                    "anyone's control. We do not promise a specific arrival "
                    "date. You are responsible for confirming that what you "
                    "order is something you may lawfully receive and hold where "
                    "you are."
                ),
            },
        ],
        "faqs": [
            {
                "q": "What currency are Alberta prices shown in?",
                "a": (
                    "Canadian dollars. Every .ca storefront in the network "
                    "displays CAD, so the number you see at checkout is the "
                    "number you are charged in."
                ),
            },
            {
                "q": "Do you have a facility in Alberta?",
                "a": (
                    "No. We serve researchers in Alberta, but we hold no office, "
                    "warehouse or laboratory in the province and make no claim "
                    "about where goods move from."
                ),
            },
            {
                "q": "What does research use only mean here?",
                "a": (
                    "It means these compounds are supplied for laboratory work "
                    "and nothing else. They are not for human or veterinary "
                    "use. We publish no guidance on use in a living subject and "
                    "make no health or outcome claims."
                ),
            },
            {
                "q": "My parcel is past day 15. What now?",
                "a": (
                    "Contact support with your order number. Border inspection "
                    "and weather are the usual causes of a parcel running past "
                    "the window, and we will tell you what we can see from our "
                    "side."
                ),
            },
        ],
    },
    {
        "slug": "british-columbia",
        "market": "CA",
        "owner": "smashfatbiolabs.ca",
        "name": "British Columbia",
        "short": "BC",
        "cities": ["Vancouver", "Victoria", "Surrey", "Kelowna", "Kamloops", "Prince George"],
        "timezone": "Pacific Time",
        "title": "British Columbia Research Peptides | Lab Use Only",
        "meta_description": (
            "Research compounds for British Columbia labs. Sold uncharacterised, "
            "CAD pricing, 10 to 15 day window. Coastal and interior handling "
            "notes. Research use only."
        ),
        "h1": "Research Compounds for British Columbia",
        "intro": (
            "British Columbia is two shipping problems in one province: a damp, "
            "mild coast and an interior that swings hard in both directions. "
            "Buyers here range from the Lower Mainland out to the Okanagan, the "
            "Island and the north. Nothing in the catalogue is intended for "
            "human or veterinary use."
        ),
        "sections": [
            {
                "h2": "What documentation exists, and what does not",
                "body": (
                    "No certificate of analysis is held for anything in "
                    "the catalogue, and no purity figure is published for "
                    "any of it. Nothing listed has been characterised "
                    "here, so identity and content are open questions "
                    "when the vial arrives. A laboratory that needs "
                    "either one settled should budget for its own "
                    "analysis before the material is used, and record the "
                    "result in its own file."
                ),
            },
            {
                "h2": "Coastal damp and interior extremes",
                "body": (
                    "A parcel landing in Vancouver or Victoria is more likely "
                    "to meet rain than frost. Bring the box inside promptly and "
                    "check that the outer packaging is dry before you open it. "
                    "The interior is a different story — Kamloops and the "
                    "Okanagan get real summer heat, and Prince George gets real "
                    "winter. Lyophilised powder tolerates a transit swing better "
                    "than a reconstituted vial does, which is why we ship it dry."
                ),
            },
            {
                "h2": "Pacific Time support",
                "body": (
                    "BC keeps Pacific Time, which puts the province at the "
                    "early end of the Canadian day. Orders placed in the BC "
                    "morning land in the same daily processing cycle as orders "
                    "from the rest of the country. Messages sent late in the BC "
                    "afternoon are usually answered on the following cycle."
                ),
            },
            {
                "h2": "Island and remote addresses",
                "body": (
                    "Deliveries to Vancouver Island, the Gulf Islands and the "
                    "north coast add a last-mile step that the mainland does "
                    "not have. The 10 to 15 day window is the same everywhere, "
                    "but the tail end of it is where an island address is most "
                    "likely to differ. Give a full civic address and a phone "
                    "number the carrier can actually reach."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you provide a certificate of analysis?",
                "a": (
                    "No. Nothing of that kind exists here to send, and "
                    "asking will not produce one. If an approval process "
                    "treats analytical documentation as a precondition, "
                    "this supply will not satisfy it."
                ),
            },
            {
                "q": "Do you ship to Vancouver Island?",
                "a": (
                    "Yes. Island addresses use the same 10 to 15 day window as "
                    "the mainland, with the ferry leg falling inside it."
                ),
            },
            {
                "q": "Does summer heat in the interior affect a shipment?",
                "a": (
                    "Compounds are shipped lyophilised, which is the form that "
                    "handles a transit swing best. Once a parcel arrives, move "
                    "it out of a hot vehicle or porch and store it as labelled."
                ),
            },
        ],
    },
    {
        "slug": "saskatchewan",
        "market": "CA",
        "owner": "smash-fat.ca",
        "name": "Saskatchewan",
        "short": "SK",
        "cities": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Swift Current"],
        "timezone": "Central Time (no seasonal change)",
        "title": "Saskatchewan Research Peptides | Research Use Only",
        "meta_description": (
            "Research peptide supply for Saskatchewan. Prairie delivery notes, "
            "CAD pricing, 10 to 15 day shipping window, no analysis claimed. "
            "Not for human use."
        ),
        "h1": "Research Peptide Supply Across Saskatchewan",
        "intro": (
            "Saskatchewan has a research character shaped by crop and soil "
            "science, and by the distances between its centres. Two cities carry "
            "most of the volume; everything else is a longer drive than a "
            "newcomer expects. We supply the province from the shared network "
            "catalogue, for laboratory research only."
        ),
        "sections": [
            {
                "h2": "A province where the clock does not move",
                "body": (
                    "Saskatchewan keeps the same clock all year while most of "
                    "the country shifts twice. In practice that means the "
                    "province lines up with Alberta for part of the year and "
                    "with Manitoba for the rest. Our processing cycle runs "
                    "daily regardless. If you are timing an order against a "
                    "cut-off, check what the offset is that week rather than "
                    "assuming it held from last month."
                ),
            },
            {
                "h2": "Long rural last miles",
                "body": (
                    "Outside Saskatoon and Regina, the final leg of a delivery "
                    "can be long, and rural route addresses are where parcels "
                    "most often go astray. Use the civic address the carrier "
                    "recognises, not a landmark description. If a site is "
                    "staffed only part of the week, say so at checkout — an "
                    "attempted delivery to an empty building costs more days "
                    "than a clear note would have."
                ),
            },
            {
                "h2": "What to confirm before you place the order",
                "body": (
                    "Four things are worth checking. First, the compound name "
                    "and vial size, since several items ship in more than one "
                    "size. Second, the delivery address and a reachable phone "
                    "number. Third, that you are permitted to receive and hold the "
                    "material where you are. That last one is on the buyer."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How long does delivery to Saskatchewan take?",
                "a": (
                    "Orders move on a 10 to 15 day window. A rural address is "
                    "more likely to land at the later end of it."
                ),
            },
            {
                "q": "Are prices in Canadian dollars?",
                "a": "Yes, all .ca storefront pricing is shown in CAD.",
            },
            {
                "q": "Do you have staff in Saskatchewan?",
                "a": (
                    "No. We serve researchers in the province and hold no "
                    "premises or staff there."
                ),
            },
        ],
    },
    {
        "slug": "manitoba",
        "market": "CA",
        "owner": "smashfat.ca",
        "name": "Manitoba",
        "short": "MB",
        "cities": ["Winnipeg", "Brandon", "Steinbach", "Portage la Prairie", "Thompson"],
        "timezone": "Central Time",
        "title": "Manitoba Research Peptides | Lab Supply, CAD",
        "meta_description": (
            "Research compounds for Manitoba labs. Winnipeg and northern "
            "delivery notes, CAD pricing, 10 to 15 day window, no purity "
            "release. Research use only."
        ),
        "h1": "Manitoba Research Compound Supply",
        "intro": (
            "Few places test a parcel harder than Manitoba. The province runs "
            "from deep winter cold to humid summer heat inside a single year, "
            "and its northern communities sit a long way past the last city. "
            "We supply Manitoba researchers with lyophilised compounds for "
            "laboratory work only."
        ),
        "sections": [
            {
                "h2": "Temperature extremes in both directions",
                "body": (
                    "A January parcel and a July parcel face opposite problems. "
                    "Cold is the milder of the two for dry material. Sustained "
                    "heat matters more, so a box left in a vehicle or on a sunny "
                    "step in midsummer is the situation worth avoiding. Bring "
                    "the parcel indoors, let a cold vial equalise before "
                    "opening, and move everything to the storage condition "
                    "printed on the label."
                ),
            },
            {
                "h2": "Winnipeg as the provincial hub",
                "body": (
                    "Most Manitoba deliveries route through the Winnipeg area, "
                    "with Brandon, Steinbach and Portage la Prairie following "
                    "close behind. Addresses in the city core and in the "
                    "surrounding industrial areas both work fine. What matters "
                    "more than the postal code is whether someone is present to "
                    "sign when the carrier arrives."
                ),
            },
            {
                "h2": "Northern Manitoba addresses",
                "body": (
                    "Thompson, Flin Flon, The Pas and the communities beyond "
                    "them add a leg that the south does not. Plan on the later "
                    "end of the 10 to 15 day window, and build in a buffer if "
                    "you are working to a schedule. Weather closures on northern "
                    "routes are a real cause of delay and are not something we "
                    "can shorten."
                ),
            },
            {
                "h2": "Pricing and currency",
                "body": (
                    "Manitoba buyers see Canadian dollars throughout. The "
                    "catalogue price shown against each compound is the current "
                    "sell price per vial, and where a reference price is also "
                    "shown it is the pre-discount figure for the same item. "
                    "There is no separate regional price list."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Will a vial be damaged by a Manitoba winter?",
                "a": (
                    "Compounds ship in lyophilised form, which is the state "
                    "that handles transit temperature swings best. Let a cold "
                    "sealed vial reach room temperature before opening it."
                ),
            },
            {
                "q": "Do northern communities take longer?",
                "a": (
                    "The window is 10 to 15 days everywhere. Northern addresses "
                    "more often land at the far end of it."
                ),
            },
            {
                "q": "What purity are the compounds?",
                "a": (
                    "No purity figure is published, because none has been "
                    "measured here. Treat what arrives as material of "
                    "unconfirmed content and establish whatever your "
                    "protocol depends on at your own bench."
                ),
            },
        ],
    },
    {
        "slug": "ontario",
        "market": "CA",
        "owner": "smashfat.ca",
        "name": "Ontario",
        "short": "ON",
        "cities": ["Toronto", "Ottawa", "Hamilton", "London", "Waterloo", "Kingston", "Windsor"],
        "timezone": "Eastern Time",
        "title": "Ontario Research Peptides | Research Use Only",
        "meta_description": (
            "Research peptide supply for Ontario. Toronto, Ottawa, Waterloo and "
            "beyond. CAD pricing, CBSA notes, 10 to 15 day window. Not for "
            "human or veterinary use."
        ),
        "h1": "Ontario Research Peptide Supply, Windsor to Ottawa",
        "intro": (
            "Ontario holds the densest concentration of research addresses in "
            "the country, strung along a corridor that runs from Windsor "
            "through the Golden Horseshoe up to Ottawa. That density changes "
            "what goes wrong with a delivery: not distance, but buildings. Our "
            "catalogue is supplied for laboratory research only."
        ),
        "sections": [
            {
                "h2": "The corridor, end to end",
                "body": (
                    "Toronto and the surrounding region carry the largest share "
                    "of Ontario orders, followed by Ottawa, Hamilton, London, "
                    "Waterloo and Kingston. Windsor sits at the southwest end "
                    "and Thunder Bay and Sudbury sit well north of the corridor "
                    "entirely. All of them are served on the same terms and the "
                    "same window."
                ),
            },
            {
                "h2": "Getting the address right in a large building",
                "body": (
                    "In dense areas the common failure is not the route, it is "
                    "the last hundred metres. A tower, a campus building or a "
                    "multi-tenant industrial unit needs a suite or unit number "
                    "and a recipient name that matches the directory or the "
                    "mailroom list. A parcel that reaches the right street and "
                    "the wrong desk can sit for days. Add a phone number the "
                    "carrier can call."
                ),
            },
            {
                "h2": "Customs on the way in",
                "body": (
                    "Inbound parcels may be subject to inspection by the Canada "
                    "Border Services Agency. That is normal and it is not "
                    "something a supplier can pre-clear or promise around. "
                    "Inspection can add days to the 10 to 15 day window. The "
                    "buyer is responsible for making sure the material is "
                    "something they may lawfully receive and hold."
                ),
            },
            {
                "h2": "What is in the catalogue",
                "body": (
                    "The same 18 items appear on every site in the network, "
                    "grouped into metabolic, mitochondrial, repair and recovery, "
                    "growth factor, neuropeptide and melanocortin categories, "
                    "plus one supply item. Ontario buyers see exactly the same "
                    "list as buyers anywhere else. Nothing is region-gated and "
                    "nothing is priced differently by province."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you ship to a university or institutional mailroom?",
                "a": (
                    "Yes, provided the address includes a building, a unit and "
                    "a recipient name the mailroom recognises. We have no "
                    "affiliation with any institution."
                ),
            },
            {
                "q": "Could my parcel be held at the border?",
                "a": (
                    "It may be subject to inspection. We cannot predict or "
                    "influence that, and we make no claims about where goods "
                    "move from."
                ),
            },
            {
                "q": "Is Ontario pricing different from the rest of Canada?",
                "a": "No. One catalogue, one CAD price list, every province.",
            },
            {
                "q": "Are these compounds for human use?",
                "a": (
                    "No. They are supplied for laboratory research only, and "
                    "not for human or veterinary use."
                ),
            },
        ],
    },
    {
        "slug": "quebec",
        "market": "CA",
        "owner": "smash-fat.ca",
        "name": "Quebec",
        "short": "QC",
        "cities": ["Montreal", "Quebec City", "Laval", "Sherbrooke", "Gatineau", "Trois-Rivieres"],
        "timezone": "Eastern Time",
        "title": "Quebec Research Peptides | Laboratory Use Only",
        "meta_description": (
            "Research compound supply for Quebec labs. Montreal, Quebec City, "
            "Sherbrooke and Gatineau. CAD pricing, 10 to 15 day window. "
            "Research use only."
        ),
        "h1": "Research Compounds for Quebec",
        "intro": (
            "Quebec's research activity clusters around Montreal, with steady "
            "volume from the capital region, the Eastern Townships and the "
            "Outaouais. Buyers here tend to be precise about paperwork, which "
            "suits us. Every compound listed is supplied for laboratory "
            "research and nothing else."
        ),
        "sections": [
            {
                "h2": "Regions served",
                "body": (
                    "Montreal and Laval account for most orders, with Quebec "
                    "City, Sherbrooke, Gatineau and Trois-Rivieres following. "
                    "Addresses in the Saguenay, Bas-Saint-Laurent and Abitibi "
                    "regions are served on the same terms, with a longer final "
                    "leg. There is no minimum order tied to any part of the "
                    "province."
                ),
            },
            {
                "h2": "Documentation and labelling",
                "body": (
                    "Vial labels are written in "
                    "English. Each label carries the compound name, the vial "
                    "size and a batch identifier, and it states that the "
                    "contents are for research use only. If you keep an internal "
                    "log, the batch identifier is the field worth recording — it "
                    "is what you would need if a purity document ever existed for it."
                ),
            },
            {
                "h2": "Eastern Time and support hours",
                "body": (
                    "Quebec runs on Eastern Time, the same as Ontario and the "
                    "US northeast. Our order batch and our support replies both "
                    "run on a daily cycle. Anything sent after the working day "
                    "in Quebec is read on the following cycle rather than the "
                    "same one."
                ),
            },
            {
                "h2": "Storage once the parcel is open",
                "body": (
                    "Compounds arrive lyophilised and sealed. Move them to the "
                    "storage condition printed on the label as soon as the "
                    "parcel is opened, and keep them out of direct light. If a "
                    "vial arrived cold, let it equalise before you break the "
                    "seal so that moisture does not condense on the stopper. "
                    "Repeated warming and cooling is worth avoiding."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Are labels available in French?",
                "a": (
                    "Vial labels are printed in English. Support can "
                    "answer written questions about what a label field "
                    "means."
                ),
            },
            {
                "q": "What identifier should I record on receipt?",
                "a": (
                    "The batch identifier on the vial label. It is the field "
                    "that any future analysis would have to reference."
                ),
            },
            {
                "q": "How long will an order to Montreal take?",
                "a": (
                    "The window is 10 to 15 days. Customs inspection can extend "
                    "it, and we do not promise a fixed arrival date."
                ),
            },
        ],
    },
    {
        "slug": "new-brunswick",
        "market": "CA",
        "owner": "where-do-i-get-peptides.ca",
        "name": "New Brunswick",
        "short": "NB",
        "cities": ["Moncton", "Saint John", "Fredericton", "Bathurst", "Miramichi"],
        "timezone": "Atlantic Time",
        "title": "New Brunswick Research Peptides | Lab Use Only",
        "meta_description": (
            "Research peptides for New Brunswick. Moncton, Saint John and "
            "Fredericton. Atlantic Time support notes, CAD pricing, 10 to 15 "
            "day window. Research use only."
        ),
        "h1": "New Brunswick Research Peptide Supply",
        "intro": (
            "New Brunswick spreads its research work across three mid-sized "
            "centres rather than concentrating it in one, and its character "
            "leans toward forestry, marine and applied science. Orders here are "
            "often smaller and more frequent than in the big provinces. "
            "Everything we list is for laboratory research use only."
        ),
        "sections": [
            {
                "h2": "Three centres, not one",
                "body": (
                    "Moncton, Saint John and Fredericton each carry a share of "
                    "provincial volume, with Bathurst, Miramichi and Edmundston "
                    "adding a steady trickle. Because no single city dominates, "
                    "there is no shortcut route that suits everyone. Every "
                    "address gets the same handling and the same window."
                ),
            },
            {
                "h2": "Atlantic Time and when to write",
                "body": (
                    "New Brunswick sits an hour ahead of Eastern Time. That "
                    "means the working day here starts and ends earlier "
                    "relative to our processing cycle than it does in Ontario. "
                    "A message sent first thing Atlantic is comfortably inside "
                    "the day's batch. One sent at the end of the Atlantic "
                    "afternoon may not be."
                ),
            },
            {
                "h2": "Combining items into one parcel",
                "body": (
                    "If you expect to need several compounds over a period, "
                    "ordering them together is usually the better call. One "
                    "parcel means one 10 to 15 day window, one trip through "
                    "customs and one delivery attempt instead of three. Vial "
                    "sizes vary by compound, so check the size on each line "
                    "before you combine them."
                ),
            },
            {
                "h2": "The terms attached to every order",
                "body": (
                    "Checkout requires an acknowledgement that the material is "
                    "for research use only. That is not a formality. These "
                    "compounds are not for human or veterinary use, we publish "
                    "no guidance on use in a living subject, and we make no "
                    "claims about what they do. The buyer is responsible for "
                    "compliance with the rules that apply where they are."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you deliver to smaller New Brunswick towns?",
                "a": (
                    "Yes, on the same 10 to 15 day window. A rural civic "
                    "address and a working phone number help the final leg."
                ),
            },
            {
                "q": "Can I split an order across two addresses?",
                "a": (
                    "No. Each order ships to one address. Place separate orders "
                    "if you need separate destinations."
                ),
            },
            {
                "q": "What does the checkout acknowledgement cover?",
                "a": (
                    "That you are buying for laboratory research use only, and "
                    "not for human or veterinary use."
                ),
            },
        ],
    },
    {
        "slug": "nova-scotia",
        "market": "CA",
        "owner": "smashfatbiolabs.ca",
        "name": "Nova Scotia",
        "short": "NS",
        "cities": ["Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow"],
        "timezone": "Atlantic Time",
        "title": "Nova Scotia Research Peptides | Research Use Only",
        "meta_description": (
            "Research compounds for Nova Scotia. Halifax and provincial "
            "coverage, coastal storage notes, no analysis claimed, CAD pricing, "
            "10 to 15 day window."
        ),
        "h1": "Research Compounds for Nova Scotia",
        "intro": (
            "Nova Scotia's research profile is heavily coastal, with ocean and "
            "marine science shaping much of the province's applied work. Almost "
            "everything routes through the Halifax area before it goes anywhere "
            "else. We supply the province for laboratory research use only."
        ),
        "sections": [
            {
                "h2": "Salt air, damp and where you keep a vial",
                "body": (
                    "Coastal buildings hold moisture, and a bench near an open "
                    "window in a shoreline building is not the best place for "
                    "sealed lyophilised material. Keep vials in the storage "
                    "condition on the label, in a closed container, away from "
                    "direct light. Salt air will not reach the contents of a "
                    "sealed vial, but it is hard on labels and on anything "
                    "left out of its packaging."
                ),
            },
            {
                "h2": "Halifax first, then everywhere else",
                "body": (
                    "Halifax and Dartmouth take the bulk of Nova Scotia orders. "
                    "Truro, New Glasgow, Sydney and the South Shore follow, and "
                    "Cape Breton addresses add a longer final leg. Nothing "
                    "about the province is far by national standards, so the "
                    "difference between a Halifax address and a rural one is "
                    "usually a day rather than a week."
                ),
            },
            {
                "h2": "What a purity number would mean, and why none appears",
                "body": (
                    "A purity number quoted by any supplier describes how "
                    "much of the material in the vial is the named "
                    "compound, measured by one method on one batch. It "
                    "describes nothing else, and it is not a claim about "
                    "what the compound does. A figure offered without a "
                    "named method and a batch reference beside it is not "
                    "worth much. None is quoted here, for any item, "
                    "because no such measurement has been made."
                ),
            },
            {
                "h2": "Atlantic Time",
                "body": (
                    "Nova Scotia keeps Atlantic Time, an hour ahead of Eastern. "
                    "Our daily order cycle does not shift by province, so the "
                    "practical effect is that the Atlantic working day is "
                    "further along when a batch is processed. Earlier messages "
                    "get read sooner."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Is there any documentation for a specific batch?",
                "a": (
                    "No. Batch-level paperwork is not produced or held "
                    "here, so there is none to request for any item. "
                    "Anything your own records need about a specific vial "
                    "has to be established at your bench and written down "
                    "there."
                ),
            },
            {
                "q": "Do Cape Breton addresses take longer?",
                "a": (
                    "Marginally. The window is 10 to 15 days across the "
                    "province and the extra distance falls inside it."
                ),
            },
            {
                "q": "Are prices in CAD?",
                "a": "Yes. Every .ca storefront shows Canadian dollars.",
            },
        ],
    },
    {
        "slug": "prince-edward-island",
        "market": "CA",
        "owner": "smashfat.ca",
        "name": "Prince Edward Island",
        "short": "PE",
        "cities": ["Charlottetown", "Summerside", "Stratford", "Montague", "Cornwall"],
        "timezone": "Atlantic Time",
        "title": "PEI Research Peptides | Prince Edward Island Supply",
        "meta_description": (
            "Research peptide supply for Prince Edward Island. Charlottetown "
            "and Summerside coverage, CAD pricing, 10 to 15 day window. "
            "Research use only."
        ),
        "h1": "Prince Edward Island Research Supply",
        "intro": (
            "Prince Edward Island is small enough that the whole province is a "
            "short drive end to end, and its applied science leans agricultural "
            "and bioscience-flavoured. Order volume here is modest, which makes "
            "planning ahead more useful than it is elsewhere. Everything listed "
            "is for laboratory research only."
        ),
        "sections": [
            {
                "h2": "Ordering in fewer, larger batches",
                "body": (
                    "Because every parcel crosses the same fixed link or ferry "
                    "leg, there is little to gain from splitting an order. "
                    "Grouping what you need into one shipment means one window, "
                    "one customs step and one delivery attempt. Check vial sizes "
                    "line by line first, since several compounds are offered in "
                    "more than one size and the price is per vial."
                ),
            },
            {
                "h2": "Charlottetown, Summerside and the rest",
                "body": (
                    "Charlottetown and the surrounding communities take most "
                    "Island deliveries, with Summerside second. Stratford, "
                    "Cornwall and Montague are close behind. Rural Island "
                    "addresses are straightforward provided the civic address "
                    "is used rather than a route description."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Is there an extra charge for Island delivery?",
                "a": (
                    "No. Pricing is the same across every Canadian storefront, "
                    "shown in CAD."
                ),
            },
            {
                "q": "How long does a PEI order take?",
                "a": (
                    "The same 10 to 15 day window that applies everywhere. "
                    "Customs inspection can extend it."
                ),
            },
            {
                "q": "Do you have an Island presence?",
                "a": (
                    "No. We serve researchers on PEI but hold no premises or "
                    "staff in the province."
                ),
            },
        ],
    },
    {
        "slug": "newfoundland-and-labrador",
        "market": "CA",
        "owner": "where-do-i-get-peptides.ca",
        "name": "Newfoundland and Labrador",
        "short": "NL",
        "cities": ["St. John's", "Mount Pearl", "Corner Brook", "Gander", "Happy Valley-Goose Bay"],
        "timezone": "Newfoundland Time",
        "title": "Newfoundland & Labrador Research Peptides",
        "meta_description": (
            "Research compounds for Newfoundland and Labrador. Half-hour time "
            "zone notes, weather buffers, CAD pricing, 10 to 15 day window. "
            "Research use only."
        ),
        "h1": "Research Peptides for Newfoundland and Labrador",
        "intro": (
            "This province runs on its own clock and its own weather. The "
            "island half concentrates around the Avalon, while Labrador is a "
            "separate logistics problem entirely. Cold-ocean and marine work "
            "colours a good deal of the research done here. All compounds are "
            "supplied for laboratory research only."
        ),
        "sections": [
            {
                "h2": "The half-hour offset",
                "body": (
                    "Newfoundland Time sits thirty minutes ahead of Atlantic "
                    "Time, which catches out anyone scheduling a call from "
                    "elsewhere. For ordering it matters little, since our batch "
                    "runs daily rather than to the minute. For support "
                    "correspondence it is worth remembering that the working "
                    "day here ends earlier than almost anywhere else in the "
                    "country."
                ),
            },
            {
                "h2": "Weather buffers are not optional",
                "body": (
                    "Wind, fog and winter storms close routes here more often "
                    "than they do inland. The shipping window remains 10 to 15 "
                    "days, but a closed route is a delay no supplier can "
                    "shorten. If a piece of work depends on material arriving, "
                    "order well before you need it rather than against the end "
                    "of the window."
                ),
            },
            {
                "h2": "Labrador addresses",
                "body": (
                    "Happy Valley-Goose Bay, Labrador City and the coastal "
                    "communities sit far past the island's road network and "
                    "carry the longest final leg in the province. Give a full "
                    "civic address, a recipient name and a phone number. Where "
                    "a community is served seasonally, plan around that season "
                    "rather than around our window."
                ),
            },
            {
                "h2": "Checking a vial on arrival",
                "body": (
                    "Open the parcel somewhere clean and dry. Confirm that the "
                    "compound name, the vial size and the batch identifier on "
                    "the label match what you ordered. Look at the stopper and "
                    "the seal. A cold vial should be left to reach room "
                    "temperature before it is opened. Record the batch "
                    "identifier in your own log while the parcel is in front of "
                    "you."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Why does my order show a different local time?",
                "a": (
                    "Newfoundland Time is offset by thirty minutes from "
                    "Atlantic Time. Order timestamps are recorded on our system "
                    "clock, not your local one."
                ),
            },
            {
                "q": "Do you ship to Labrador?",
                "a": (
                    "Yes. Labrador carries the longest final leg in the "
                    "province, so allow buffer beyond the 10 to 15 day window "
                    "if timing matters."
                ),
            },
            {
                "q": "What should I check when the parcel arrives?",
                "a": (
                    "Compound name, vial size, batch identifier and seal "
                    "condition. Log the batch identifier before the packaging "
                    "is discarded."
                ),
            },
        ],
    },
    {
        "slug": "yukon",
        "market": "CA",
        "owner": "smash-fat.ca",
        "name": "Yukon",
        "short": "YT",
        "cities": ["Whitehorse", "Dawson City", "Watson Lake", "Haines Junction"],
        "timezone": "Yukon Time (no seasonal change)",
        "title": "Yukon Research Peptides | Northern Lab Supply",
        "meta_description": (
            "Research compound supply for Yukon. Whitehorse and territorial "
            "coverage, cold-transit notes, CAD pricing, 10 to 15 day window. "
            "Research use only."
        ),
        "h1": "Yukon Research Supply for Northern Laboratories",
        "intro": (
            "Yukon research is a small, practical world where most supply comes "
            "in from a long way off and nobody expects it quickly. Whitehorse "
            "anchors the territory and everything else runs off the highway "
            "network from there. We supply the territory for laboratory "
            "research use only."
        ),
        "sections": [
            {
                "h2": "Extreme cold in transit",
                "body": (
                    "A parcel heading north in midwinter will spend time below "
                    "freezing. Dry lyophilised material handles that better "
                    "than most things in a courier truck, which is one reason "
                    "it ships in that form. The step that matters is at your "
                    "end: bring the box inside, let the sealed vial warm to "
                    "room temperature, then open it and store it as the label "
                    "states."
                ),
            },
            {
                "h2": "A clock that stays put",
                "body": (
                    "Yukon keeps the same time all year rather than shifting "
                    "seasonally. The gap between Whitehorse and our processing "
                    "cycle therefore changes twice a year even though your own "
                    "clock does not. If you are timing an order against a "
                    "cut-off, check the current offset rather than assuming the "
                    "one you used last season."
                ),
            },
            {
                "h2": "Planning around a long final leg",
                "body": (
                    "Whitehorse is the straightforward case. Dawson City, "
                    "Watson Lake, Haines Junction and the smaller communities "
                    "add road time on top, and winter road conditions add more. "
                    "The 10 to 15 day window still applies, but northern orders "
                    "tend to sit at the far end of it. Order before you are "
                    "short rather than after."
                ),
            },
            {
                "h2": "Customs on an inbound parcel",
                "body": (
                    "Parcels entering Canada may be subject to inspection by "
                    "the Canada Border Services Agency, regardless of the "
                    "destination territory. We cannot pre-clear a shipment and "
                    "we make no claim about where goods move from. The buyer is "
                    "responsible for confirming they may lawfully receive and "
                    "hold the material."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Will freezing damage a vial in transit?",
                "a": (
                    "Compounds ship lyophilised, the form that best tolerates a "
                    "transit temperature swing. Let a cold sealed vial reach "
                    "room temperature before opening."
                ),
            },
            {
                "q": "How far ahead should I order in Yukon?",
                "a": (
                    "Assume the far end of the 10 to 15 day window, and add "
                    "buffer in winter when road conditions can close routes."
                ),
            },
            {
                "q": "Is there a northern surcharge?",
                "a": (
                    "Pricing is the same across all Canadian storefronts, shown "
                    "in CAD, with no territorial price list."
                ),
            },
        ],
    },
    {
        "slug": "northwest-territories",
        "market": "CA",
        "owner": "smashfatbiolabs.ca",
        "name": "Northwest Territories",
        "short": "NT",
        "cities": ["Yellowknife", "Hay River", "Inuvik", "Fort Smith", "Norman Wells"],
        "timezone": "Mountain Time",
        "title": "Northwest Territories Research Peptides | NT Supply",
        "meta_description": (
            "Research compounds for the Northwest Territories. Yellowknife and "
            "fly-in community notes, CAD pricing, 10 to 15 day window. "
            "Research use only."
        ),
        "h1": "Research Peptides for the Northwest Territories",
        "intro": (
            "Supply into the Northwest Territories is governed less by distance "
            "than by season. Some communities are on the road network, some are "
            "reached by air, and some change category depending on the month. "
            "Yellowknife is the practical hub. Everything we list is for "
            "laboratory research only."
        ),
        "sections": [
            {
                "h2": "Road, air and the seasons in between",
                "body": (
                    "Yellowknife, Hay River and Fort Smith sit on the road "
                    "network. Inuvik, Norman Wells and the smaller communities "
                    "depend more heavily on air freight, and winter road "
                    "seasons shift what is reachable and how. None of that "
                    "changes our 10 to 15 day window, but it does change where "
                    "inside that window a parcel is likely to land."
                ),
            },
            {
                "h2": "Mountain Time in the territory",
                "body": (
                    "Most of the territory keeps Mountain Time, the same as "
                    "Alberta. Our order batch runs on a daily cycle, so the "
                    "practical guidance is the same as it is further south: get "
                    "an order in during the working day rather than late at "
                    "night if you want it in that day's batch."
                ),
            },
            {
                "h2": "Consolidating what you need",
                "body": (
                    "Northern buyers get more out of one larger order than "
                    "several small ones. Each parcel is its own window, its own "
                    "customs step and its own final leg. Grouping compounds "
                    "into one order removes repeated waiting. Confirm vial sizes before "
                    "you combine, since sizes differ by compound."
                ),
            },
            {
                "h2": "Storage once it lands",
                "body": (
                    "Move vials into the storage condition printed on the label "
                    "as soon as the parcel is opened, and keep them out of "
                    "direct light. In a building where heating varies through "
                    "the day, a stable interior spot is better than a shelf "
                    "near an exterior wall. Avoid repeated cycles of warming "
                    "and cooling."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you deliver to fly-in communities?",
                "a": (
                    "Yes, subject to the carrier serving the community. Expect "
                    "the far end of the 10 to 15 day window and allow buffer."
                ),
            },
            {
                "q": "Can I combine several compounds in one order?",
                "a": (
                    "Yes, and in the north it is usually the better approach. "
                    "One parcel means one window and one final leg."
                ),
            },
            {
                "q": "Do you have a northern depot?",
                "a": (
                    "No. We serve researchers in the territory and hold no "
                    "premises there. We make no claim about where goods move "
                    "from."
                ),
            },
        ],
    },
    {
        "slug": "nunavut",
        "market": "CA",
        "owner": "where-do-i-get-peptides.ca",
        "name": "Nunavut",
        "short": "NU",
        "cities": ["Iqaluit", "Rankin Inlet", "Cambridge Bay", "Arviat", "Baker Lake"],
        "timezone": "Eastern, Central and Mountain Time",
        "title": "Nunavut Research Peptides | Arctic Lab Supply",
        "meta_description": (
            "Research compound supply for Nunavut. Air freight realities, "
            "multiple time zones, CAD pricing, 10 to 15 day window plus buffer. "
            "Research use only."
        ),
        "h1": "Research Compound Supply for Nunavut",
        "intro": (
            "Nunavut is the hardest destination in the country to plan supply "
            "for, and the honest advice is to order earlier than you think you "
            "need to. Communities are reached by air, weather governs the "
            "schedule, and the territory spans more than one time zone. All "
            "material is supplied for laboratory research only."
        ),
        "sections": [
            {
                "h2": "Air freight and what it means for timing",
                "body": (
                    "There is no road network linking Nunavut communities to "
                    "the south, so the final leg is a flight. Flights are "
                    "weather-dependent and a missed connection can mean waiting "
                    "for the next scheduled service rather than the next hour. "
                    "Our window is 10 to 15 days like everywhere else, and "
                    "Nunavut is the place where it is most likely to be "
                    "exceeded."
                ),
            },
            {
                "h2": "More than one time zone",
                "body": (
                    "The territory spans Eastern, Central and Mountain Time "
                    "depending on the community. Iqaluit and Rankin Inlet do "
                    "not keep the same clock. When you write to support, saying "
                    "which community you are in is more useful than saying what "
                    "time it is where you are."
                ),
            },
            {
                "h2": "Build a buffer into the plan",
                "body": (
                    "Take the window as a floor rather than a forecast. If "
                    "material is needed for a scheduled piece of work, order "
                    "several weeks ahead and order the full quantity at once. A "
                    "second parcel sent to correct a short order will take as "
                    "long as the first one did, and possibly longer if the "
                    "season has turned."
                ),
            },
            {
                "h2": "Keeping your own records",
                "body": (
                    "Where supply is slow, good record keeping is worth more. "
                    "Log the compound name, vial size, batch identifier and "
                    "arrival date for everything you receive, and keep the "
                    "record alongside it. That way an audit or a "
                    "question about a specific vial can be answered from your "
                    "own file rather than by waiting on correspondence."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you deliver to every Nunavut community?",
                "a": (
                    "Delivery depends on the carrier serving the community. "
                    "Give the full address at checkout and support will tell "
                    "you if there is a problem."
                ),
            },
            {
                "q": "How far ahead should I order?",
                "a": (
                    "Well ahead. The 10 to 15 day window is our standard, and "
                    "Nunavut is where weather and flight schedules most often "
                    "push past it."
                ),
            },
            {
                "q": "Is pricing different in the territory?",
                "a": (
                    "No. One CAD price list applies across every Canadian "
                    "storefront."
                ),
            },
            {
                "q": "What records should I keep on receipt?",
                "a": (
                    "Compound name, vial size, batch identifier and arrival "
                    "date, kept in your own receiving record."
                ),
            },
        ],
    },

    # ------------------------------------------------------------------
    # ALBERTA CITY PAGES — peptidesalberta.ca only.
    #
    # These hang off the Alberta province page via "parent". They carry NO
    # compliance boilerplate section and no "do you have premises here" or
    # "can you send a COA" FAQ, even though every one of them was drafted
    # with both. Two independent distinctness audits found the same thing:
    # the local reasoning was genuinely different city to city, but the
    # policy paragraph was one sentence run through a thesaurus six times,
    # and that repetition — not the local copy — was the doorway-page
    # signature. Rewriting boilerplate six ways does not fix it; not
    # repeating it does. The research-use notice, the delivery window and
    # the currency are rendered on every region page by
    # templates/partials/_region.html, and the province page answers the
    # premises and documentation questions once, for all of Alberta.
    #
    # Section and FAQ counts differ per page on purpose (4/3/3/4/3/4 and
    # 2/2/3/2/3/2). A uniform shape is itself a fingerprint.
    # ------------------------------------------------------------------
    {
        "slug": "calgary",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Calgary",
        "short": "Calgary",
        "cities": ["Calgary"],
        "timezone": "Mountain Time",
        "title": "Research Peptides in Calgary | Addressing and Receiving",
        "meta_description": (
            "A Calgary label needs the quadrant, the bay number and the "
            "tenant name, or a driver is guessing. Addressing and "
            "receiving notes for research-use material."
        ),
        "h1": (
            "Research Peptides in Calgary, Alberta: Addressing and "
            "Receiving"
        ),
        "intro": (
            "A Calgary parcel goes astray for ordinary reasons: the label "
            "names a building nobody at the bench works in, or the door "
            "it reaches has nobody behind it that afternoon. Both are "
            "cheap to prevent at checkout and awkward to unpick "
            "afterwards. Everything listed on peptidesalberta.ca is bench "
            "reference material for in vitro and analytical work, is not "
            "for use in humans or animals, and carries no claim about "
            "what it does. What follows is the receiving procedure for "
            "this city: how to write the address, what happens at a tower "
            "mailroom or an industrial dock, and what to log when the box "
            "lands."
        ),
        "sections": [
            {
                "h2": (
                    "The suite that pays and the bay that receives are "
                    "rarely the same door"
                ),
                "body": (
                    "Plenty of bench work in this city sits behind a "
                    "company door rather than a public one, and "
                    "organisations built that way often run a split "
                    "footprint: registered office and purchasing in one "
                    "part of town, benches in leased space somewhere else "
                    "entirely. That split produces one specific failure, "
                    "and it repeats. Purchasing types the head-office "
                    "suite into the delivery field out of habit, because "
                    "that is the address on every other form they fill in "
                    "that week. The parcel then lands in a tower mailroom "
                    "on the far side of the river from the bench that "
                    "ordered it. Procedure: if billing and receiving are "
                    "different addresses, enter them as different "
                    "addresses. Nothing is rerouted once a parcel is "
                    "moving, and a driver holding an ambiguous label does "
                    "not resolve it in your favour."
                ),
            },
            {
                "h2": (
                    "Quadrant, street versus avenue, bay number: three "
                    "checks before you submit"
                ),
                "body": (
                    "Every Calgary civic address ends in a quadrant, NE, "
                    "NW, SE or SW, and the same street number on the same "
                    "street name genuinely exists in more than one of "
                    "them. Drop the suffix and the label is ambiguous. "
                    "The ambiguity usually gets resolved by a driver "
                    "standing at the wrong end of the city. Second check: "
                    "streets run north to south, avenues east to west. "
                    "Transposing them produces a real address in the "
                    "wrong place, which is harder to catch than an "
                    "address that simply fails validation. Third check: "
                    "the bay or unit. In the industrial parks one civic "
                    "address can front a long row of tenants, and the bay "
                    "number is the only field separating yours from the "
                    "shop four doors down. Put the tenant name on as "
                    "well, spelled the way the building directory or the "
                    "gate list spells it, not the way the letterhead "
                    "does."
                ),
            },
            {
                "h2": (
                    "Mailrooms, dock hours and who is standing there to "
                    "sign"
                ),
                "body": (
                    "Downtown towers: couriers deliver to a central "
                    "mailroom or to a dock off the lane, not to a suite "
                    "door. Internal handling then adds a leg you do not "
                    "control and occasionally a day you did not budget. "
                    "If the building matches parcels against its own "
                    "directory, the directory name is the name that "
                    "belongs on the order. Industrial parks: shipping and "
                    "receiving offices frequently close hours before the "
                    "rest of the site does. A driver arriving after the "
                    "receiving door is locked has no one to hand to, "
                    "because the front of a building designed around "
                    "trucks is not staffed for walk-ins. Some sites also "
                    "check drivers in at a gate, which spends time out of "
                    "an already narrow window. Signatures: a person has "
                    "to be present to give one. Name an individual and a "
                    "direct phone number on the order rather than a "
                    "department, put your receiving hours and any gate "
                    "procedure in the order notes, and state plainly if "
                    "the site has no attended receiving at all. That "
                    "information does work before dispatch. After a first "
                    "attempt has failed it does almost none."
                ),
            },
            {
                "h2": (
                    "Chinook swings and the thermal history nobody wrote "
                    "down"
                ),
                "body": (
                    "Chinooks are ordinary Calgary weather, not a turn of "
                    "phrase. A warm westerly comes over the mountains, "
                    "the air warms hard across a few hours, then cools "
                    "back once the wind quits. A single day can run from "
                    "thaw to hard cold and back again. Nothing in a "
                    "delivery chain is climate controlled, and a doorstep "
                    "least of all. Material travels as a sealed "
                    "lyophilised vial. A vial that sits through a warm "
                    "afternoon and the cold night behind it has been "
                    "through a thermal cycle no instrument watched. We "
                    "cannot reconstruct that cycle afterwards, and we "
                    "make no representation about the condition of "
                    "anything once it has left our hands. So write it "
                    "down. Time of receipt. Whether the parcel was "
                    "outdoors, and for how long. Conditions across that "
                    "interval. Visible state of the outer box, the vial "
                    "and the seal before any of it goes into your own "
                    "storage. That log is the only thermal history the "
                    "vial has, so file it with the material's paperwork. "
                    "One scheduling note: an unattended site heading into "
                    "a weekend means two nights outdoors before anyone "
                    "looks at the box. Which day inside the window a "
                    "driver turns up is not something either of us sets, "
                    "so the answer is coverage rather than timing: have "
                    "somebody available across the whole window, or "
                    "nominate an address that is attended on every "
                    "working day."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "What exactly goes in the address fields for a "
                    "Calgary delivery?"
                ),
                "a": (
                    "All of it: street number, street or avenue name, the "
                    "quadrant suffix, the bay or unit, and the tenant "
                    "name as the building directory or gate list carries "
                    "it. Add a named contact with a direct line rather "
                    "than a switchboard. A missing quadrant and a swapped "
                    "street-for-avenue are the two errors that send a "
                    "driver across the city, and both cost nothing to "
                    "catch before you submit."
                ),
            },
            {
                "q": (
                    "A parcel sat outside our door through a chinook "
                    "swing. What goes in the log?"
                ),
                "a": (
                    "Delivery time, hours spent outdoors, conditions "
                    "across that interval, and the state of the outer "
                    "packaging, the vial and the seal at opening. We "
                    "cannot tell you what that cycling did to the "
                    "contents. Nothing was characterised on our end to "
                    "begin with, so the log is not a comparison against a "
                    "baseline; it is the handling record your own file "
                    "needs in order to be honest about provenance."
                ),
            },
        ],
    },
    {
        "slug": "edmonton",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Edmonton",
        "short": "Edmonton",
        "cities": ["Edmonton"],
        "timezone": "Mountain Time",
        "title": "Edmonton Research Peptides: Ordering and Winter Receiving",
        "meta_description": (
            "Receiving research peptides at an Edmonton address in "
            "winter: after-hours cold at the door, river valley delivery "
            "notes, and a 10 to 15 day window."
        ),
        "h1": "Edmonton: Research Peptide Orders and Winter Receiving",
        "intro": (
            "Cold is the first thing to plan for on an Edmonton order. "
            "Everything listed is laboratory reference material, intended "
            "for research work at the bench. It is not for human use and "
            "not for veterinary use, and none of it belongs anywhere near "
            "a living subject. The rest of this page is practical. It "
            "covers deep cold at the receiving end, orders that carry on "
            "north, addresses on both banks of the river valley, and what "
            "to write down when a box lands."
        ),
        "sections": [
            {
                "h2": "When the cold does not let up",
                "body": (
                    "Edmonton's issue is not one cold night. It is the "
                    "run of them. A midwinter thaw is not something to "
                    "build a plan around this far north. A cold spell can "
                    "hold for days, from one end to the other, with no "
                    "real recovery in between. That matters at the door "
                    "more than on the road. A parcel lands late in the "
                    "afternoon. It waits in an unheated vestibule. Nobody "
                    "is back until morning. That is twelve hours or more "
                    "at whatever the outside air is doing, and in a "
                    "stretch like this the air is not doing anything "
                    "kind. A mailroom that empties at five gives you the "
                    "same result. So assume the material may sit at "
                    "ambient temperature at some point before it reaches "
                    "your bench. It can go either way, warm or cold. "
                    "Design the receiving end around that assumption "
                    "rather than around a best case."
                ),
            },
            {
                "h2": "When Edmonton is a stop, not the end of the trip",
                "body": (
                    "A fair share of Edmonton delivery addresses are not "
                    "where the work happens. The box arrives in the city, "
                    "waits a few days, then travels north with whoever is "
                    "driving or flying up. If that is your setup, read "
                    "our 10 to 15 day window as covering the trip to the "
                    "address written on the order. Nothing beyond it. The "
                    "second leg is yours to schedule, and it is usually "
                    "the leg with the least slack in it. We keep no "
                    "facility in Edmonton. We cannot hold a parcel, stage "
                    "one, or consolidate several on your behalf. Groups "
                    "that need a holding point set one up themselves. A "
                    "colleague's office works. So does a receiving desk, "
                    "or a private address where somebody is reliably in."
                ),
            },
            {
                "h2": "Addresses on both banks of the river valley",
                "body": (
                    "The North Saskatchewan splits the city. An address "
                    "on either bank is ordinary. The side makes no "
                    "difference to an order. It makes a difference to a "
                    "driver's day. Two addresses can look close on a map "
                    "and still sit across the valley from one another. In "
                    "winter the crossing is where a route slows down. So "
                    "write a real delivery note. Name the nearest "
                    "crossing, the building entrance, and the door that "
                    "is actually unlocked in January. A postal code by "
                    "itself says very little. Where you have a choice, "
                    "take the building with a staffed reception over a "
                    "residential vestibule or an after-hours dock. The "
                    "reason is in the first section."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "Our loading dock is unheated and the mailroom shuts "
                    "at five. What do you suggest for a January delivery?"
                ),
                "a": (
                    "Send it to an address where somebody is there "
                    "through the afternoon, or to a building with a "
                    "staffed reception rather than an unattended dock or "
                    "vestibule. A long stretch at ambient between drop- "
                    "off and pickup is the main thing worth designing "
                    "around in an Edmonton winter. Add a clear delivery "
                    "note with the entrance and any access instructions. "
                    "Then move the parcel into your intended storage as "
                    "soon as it is in hand, and log the state it arrived "
                    "in."
                ),
            },
            {
                "q": (
                    "The address is in Edmonton but the work happens "
                    "further north. Is that a problem?"
                ),
                "a": (
                    "No. A delivery address is just a delivery address, "
                    "and we do not need to know what happens after it. We "
                    "do not arrange or quote the onward leg, so the drive "
                    "or flight north sits outside our window entirely. "
                    "Schedule it separately in your own planning."
                ),
            },
        ],
    },
    {
        "slug": "red-deer",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Red Deer",
        "short": "Red Deer",
        "cities": ["Red Deer"],
        "timezone": "Mountain Time",
        "title": "Research Peptides for Red Deer and Central Alberta",
        "meta_description": (
            "Why a Red Deer parcel scans in a larger centre before it "
            "reaches you, what the final leg looks like at an address "
            "this size, and how to order around it."
        ),
        "h1": "Research Peptides for Red Deer and Central Alberta",
        "intro": (
            "There is a moment in a Red Deer delivery when the tracking "
            "page stops making sense: it shows a city that is not Red "
            "Deer, the last scan has not moved since yesterday, and there "
            "is no obvious way to tell whether the parcel is fine or "
            "stuck. Usually it is fine, and the reason has far more to do "
            "with how freight moves along the central Alberta corridor "
            "than with anything about the order itself. What follows "
            "explains that, and sets out the plain limits on what we "
            "sell: reference material for controlled laboratory research "
            "by qualified personnel, never for human or veterinary use, "
            "and never to be given to a living subject of any kind."
        ),
        "sections": [
            {
                "h2": "A scan in a bigger city is the route, not a hold-up",
                "body": (
                    "Red Deer sits near the middle of the run between "
                    "Calgary and Edmonton, and that position shapes an "
                    "order more than anything else about the address. "
                    "Carrier networks in this province are built around "
                    "the two large centres, so once a parcel is inside "
                    "the provincial network on its way to a central "
                    "Alberta address, it is normally sorted at one of "
                    "them and then carried up or down the corridor on a "
                    "line-haul leg. What you are watching on the tracking "
                    "page is that structure doing exactly what it was "
                    "designed to do. A scan in a larger centre appearing "
                    "a day or two ahead of the Red Deer scan is the "
                    "ordinary shape of the final leg, not a detour and "
                    "not a stall. Plan on a span of 10 to 15 days between "
                    "placing an order and having the box in front of you. "
                    "That span is the honest unit of measurement here; we "
                    "cannot narrow it to a particular day on a calendar, "
                    "and a scan that sits still for a day inside it is "
                    "not yet evidence of anything. Let the range finish "
                    "running before you read a quiet tracking page as a "
                    "fault."
                ),
            },
            {
                "h2": (
                    "What the final leg tends to look like at an address "
                    "this size"
                ),
                "body": (
                    "An address in a centre this size usually has a final "
                    "leg with few stages in it. A parcel headed for Red "
                    "Deer commonly arrives at a door or a dock on a "
                    "single daily run and stays in one set of hands the "
                    "whole way, rather than moving through a tower "
                    "mailroom, a security desk, a booked freight elevator "
                    "and a floor reception before it reaches the person "
                    "waiting on it. That simplicity is worth protecting, "
                    "and it takes almost no effort to protect. Put a "
                    "named person on the address line together with a "
                    "room or bay number rather than a company name on its "
                    "own, and let whoever signs at the door know a box is "
                    "due inside the window. A short chain only helps if "
                    "the last link knows what it is holding. When "
                    "something does go sideways in a place this size, the "
                    "usual reason is that the parcel landed with someone "
                    "who had no idea it was coming."
                ),
            },
            {
                "h2": (
                    "Ordering at the pace applied and agricultural work "
                    "actually moves"
                ),
                "body": (
                    "Applied and agricultural science is the everyday "
                    "backdrop across central Alberta, and purchasing in "
                    "those settings runs on paperwork rather than "
                    "impulse: a budget line, a purchase order number, an "
                    "itemised invoice, a receiving log at the door. That "
                    "pace suits us fine. Nobody here will press you to "
                    "move ahead of your own approvals, and an order "
                    "placed the day your process clears it is an order "
                    "placed on time. The surrounding programme changes "
                    "nothing about the boundary, and the boundary is "
                    "firm. What we supply is reference material for in- "
                    "vitro and analytical work by qualified personnel in "
                    "a controlled setting. It is not a human product and "
                    "not a veterinary one, and it has no place on a "
                    "field, in a feed line, or in any animal. Nothing on "
                    "this site describes such use, supports it, or should "
                    "be read as an invitation to attempt it."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "Why did tracking show my parcel in Calgary before it "
                    "showed anything in Red Deer?"
                ),
                "a": (
                    "Because that is the route. Provincial carrier "
                    "networks run through the two large centres, so a "
                    "parcel bound for a central Alberta address is "
                    "normally sorted at one of them and then moved along "
                    "the corridor on a line-haul leg. Seeing Calgary or "
                    "Edmonton a day or two before the Red Deer scan is "
                    "the expected sequence rather than a sign of a "
                    "misdirected box. Let the 10 to 15 day span play out "
                    "before you treat a static scan as trouble."
                ),
            },
            {
                "q": (
                    "Can you invoice against a purchase order number, in "
                    "Canadian dollars?"
                ),
                "a": (
                    "Yes. Pricing is in Canadian dollars, and the invoice "
                    "can carry your purchase order number and cost centre "
                    "so it drops straight into a receiving file. If your "
                    "approval process also needs supporting documentation "
                    "attached to the vendor record before a PO is raised, "
                    "read the documentation note on the Alberta page first "
                    "— it will tell you whether this clears your process."
                ),
            },
            {
                "q": (
                    "We run an agricultural operation. Could any of this "
                    "be used on livestock?"
                ),
                "a": (
                    "No. Nothing sold here is a veterinary or human "
                    "product, and none of it may be administered to an "
                    "animal, on a farm or anywhere else. It is reference "
                    "material for in-vitro and analytical research "
                    "conducted by qualified personnel, and that is the "
                    "only basis on which it is offered."
                ),
            },
        ],
    },
    {
        "slug": "lethbridge",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Lethbridge",
        "short": "Lethbridge",
        "cities": ["Lethbridge"],
        "timezone": "Mountain Time",
        "title": "Research Peptides in Lethbridge | Delivery and Handling",
        "meta_description": (
            "A parcel left at a Lethbridge door meets the wind. Choosing "
            "a receiving address that gets it indoors, and ordering "
            "around the plot season."
        ),
        "h1": "Research Peptides for Lethbridge, Alberta",
        "intro": (
            "Set a light parcel on a concrete step in Lethbridge and the "
            "wind starts working on it before anyone comes out to collect "
            "it. That is the practical shape of ordering here. "
            "peptidesalberta.ca sends research stock by mail to people "
            "working in Lethbridge and the irrigation districts around "
            "it, and the leg of the trip that goes wrong is usually the "
            "last two metres. Below: where a box should land, when to "
            "send an order when the calendar is built around field work, "
            "and what this material is not — bench reference stock for "
            "research work, never for human or veterinary use."
        ),
        "sections": [
            {
                "h2": "What the wind does to a box on a step",
                "body": (
                    "Wind in this corner of the province is load-bearing, "
                    "not a line in a forecast. It runs long and steady "
                    "across open ground, it picks up speed through the "
                    "coulees when a chinook is on, and it goes to work on "
                    "anything left in the open. A parcel put down at an "
                    "exposed door is an object with a large flat side and "
                    "almost no weight holding it there. It tips. It "
                    "slides off the step and wedges against a railing or "
                    "a fence. It rotates until one corner is taking "
                    "everything, and wind-carried grit sands that corner "
                    "while the box waits. Tape lifts at the edge. A seam "
                    "that was square when the driver walked away has gone "
                    "soft by the time somebody notices the delivery. None "
                    "of that is exotic and none of it is anyone's fault. "
                    "It is simply what happens to light cardboard sitting "
                    "outdoors here, and it is why the address you choose "
                    "does more for a shipment than the packaging around "
                    "it does."
                ),
            },
            {
                "h2": "Plot season decides when the order goes in",
                "body": (
                    "Lethbridge sits in dry country organised around "
                    "canals and the crops they feed, and much of the "
                    "applied science follows from that: agronomy trials "
                    "and plot work, soil chemistry, weed and insect work "
                    "tied to field crops, water sampling that runs with "
                    "the canal season. Peptide reagents are not the "
                    "centre of a programme like that. But benches "
                    "attached to field research still run assay work and "
                    "still buy consumables, and this page is written for "
                    "whoever fills the order and whoever signs off on it. "
                    "Delivery moves inside a span of 10 to 15 days. No "
                    "particular day inside that span is committed to, and "
                    "nothing here will be written down as a calendar "
                    "date, because that would be a guess dressed up as a "
                    "promise. From the start of plot work through harvest "
                    "the building thins out, and a box that arrives on a "
                    "day when nobody is inside is a box on a step in the "
                    "wind. So fix the week the vial has to be sitting on "
                    "the bench, lay the 10 to 15 days in front of that "
                    "week, and add whatever days the receiving door is "
                    "unattended. Place the order while somebody is still "
                    "reliably in the building rather than in the middle "
                    "of a field push. Every figure on the product pages "
                    "is a Canadian dollar amount, which is the currency "
                    "the requisition gets written in anyway."
                ),
            },
            {
                "h2": "Dry air goes after the labelling",
                "body": (
                    "Southern Alberta air is dry for most of the year, "
                    "and dryness gets blamed for a great deal. How the "
                    "contents of a vial behave in it is not something we "
                    "have any basis to describe, and we do not describe "
                    "it. What can be said is that the closure, rather "
                    "than the room, is the boundary the contents sit "
                    "behind, so an intact seal is the thing worth "
                    "checking. Where dry air shows up plainly is in the "
                    "small physical business around the vial. Static "
                    "jumps to weigh paper and to plastic. Adhesive labels "
                    "curl at one corner over a winter and then let go. "
                    "Marker ink on a cap goes brittle and flakes off "
                    "under a gloved thumb. That is labelling and handling "
                    "rather than anything we can tell you about what is "
                    "inside; all of it decides whether anyone can still "
                    "name what they are holding six months from now. The "
                    "stresses worth watching are ordinary ones: a room "
                    "that bakes in July and runs cold in January, direct "
                    "light lying across a south-facing bench through an "
                    "afternoon, and whether a container has been opened. "
                    "Leaving stock out on an open bench because the air "
                    "is dry is the habit to break — not on account of "
                    "humidity, but because an open bench sits exposed to "
                    "whatever the room happens to be doing."
                ),
            },
            {
                "h2": "Choosing the door the box arrives at",
                "body": (
                    "We print the address that comes in with the order. "
                    "Past that point the final leg belongs to the "
                    "courier, and nothing we write on a label decides "
                    "where a driver sets a package down. So the address "
                    "carries the load. A staffed reception, a "
                    "departmental mailroom, a bay on the sheltered side "
                    "of the building — anywhere the box gets picked up "
                    "and carried inside within minutes instead of "
                    "standing outdoors for an afternoon. A unit number, a "
                    "building name, a bay number and a person's name on "
                    "the line each cut a little more time off how long "
                    "the parcel spends in the open. Once it is in hand, "
                    "open it in front of whoever signed for it. Crushed "
                    "corners, a sprung seam, a seal that has already been "
                    "broken — write down what you can see while the box "
                    "is still on the desk, alongside the date it came in, "
                    "the way you would for any other incoming stock."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "Our crew is out on plots from spring through "
                    "harvest. When should we put an order in?"
                ),
                "a": (
                    "Put the 10 to 15 day span in front of the week you "
                    "need the material on the bench, then add the days "
                    "the building is effectively empty. The order that "
                    "goes badly is the one that lands while everyone is "
                    "at a site and the box waits at a door. Product page "
                    "figures are in Canadian dollars if a requisition has "
                    "to be drafted before anything is ordered."
                ),
            },
            {
                "q": (
                    "Our receiving door faces west and takes the full "
                    "wind. Can the parcel be flagged for a sheltered "
                    "spot?"
                ),
                "a": (
                    "We can print whatever address you send us, but where "
                    "a driver puts the box down is outside anything we "
                    "control. Given what an exposed step does to "
                    "cardboard here, the fix that holds is an address "
                    "staffed through the working day, or a mailroom or "
                    "bay tucked out of the prevailing wind, so the parcel "
                    "gets carried in instead of left."
                ),
            },
        ],
    },
    {
        "slug": "medicine-hat",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Medicine Hat",
        "short": "Medicine Hat",
        "cities": ["Medicine Hat"],
        "timezone": "Mountain Time",
        "title": "Research Peptides in Medicine Hat | Summer Delivery",
        "meta_description": (
            "A July box left on a sunny step is the real Medicine Hat "
            "delivery problem. Planning who collects it, and ordering "
            "around a lab that empties in August."
        ),
        "h1": (
            "Research peptide orders arriving in Medicine Hat during a "
            "hot week"
        ),
        "intro": (
            "Order to a Medicine Hat address and the thing that tends to "
            "complicate the last hundred metres is not frost. It is a "
            "bright, still afternoon in July, a delivery that lands at "
            "one o'clock, and nobody home until six. Everything listed on "
            "the storefront is bench reference stock for laboratory work "
            "only; it is not for people or animals, and nothing written "
            "here describes putting it into anything alive. What follows "
            "is mostly about the gap between the courier leaving and you "
            "picking the box up."
        ),
        "sections": [
            {
                "h2": (
                    "A hot step, a hot cab, and the case for getting to "
                    "the box early"
                ),
                "body": (
                    "Shipping advice aimed at this province almost always "
                    "assumes the enemy is cold. Down in this corner of "
                    "Alberta the months that deserve a plan are the "
                    "clear, dry ones, when the sky holds its colour for a "
                    "week straight and the light hangs around well past "
                    "supper. A carton on a south-facing step at two in "
                    "the afternoon is not sitting at whatever the "
                    "forecast said. The concrete has been soaking up sun "
                    "since morning, the door is doing the same, and the "
                    "cardboard is happily absorbing the rest. Same story "
                    "for a parcel that gets collected on the way through "
                    "and then rides around in a closed vehicle on an open "
                    "lot while the rest of the errands get done. We make "
                    "no representation about how the contents behave "
                    "through any of that, and after the fact you cannot "
                    "reconstruct it either. That is the narrow, practical "
                    "point: from the moment the box is outside and "
                    "unattended, its temperature history stops being "
                    "anything you can put in writing. Bringing it in "
                    "promptly is the one part of that you own."
                ),
            },
            {
                "h2": (
                    "Sorting out the handoff before anything is on its "
                    "way"
                ),
                "body": (
                    "Nobody can tell you the hour a driver will pull up, "
                    "and we are not going to pretend we can. What you can "
                    "settle beforehand is where the box waits when you "
                    "are not standing at the door. A delivery instruction "
                    "naming an actual sheltered spot — a shaded side "
                    "entrance, a covered breezeway, a reception desk "
                    "inside the building — does more good than a note "
                    "asking the driver to take care. Putting a second "
                    "name on the file means the parcel is not hostage to "
                    "one person's schedule. And plenty of carriers will "
                    "hold a parcel at their depot for collection, which "
                    "at least keeps it under a roof until somebody drives "
                    "over. On timing: figure on 10 to 15 days. Nothing in "
                    "that range fixes an hour or a square on the calendar "
                    "for you, so build it into the schedule as slack "
                    "rather than treating it as something to hold us to. "
                    "Figures on the storefront are in Canadian dollars. "
                    "If a particular week in July or August already has "
                    "work booked against it, start from that week and "
                    "give yourself generous room ahead of it, so the "
                    "parcel lands while the building still has people in "
                    "it."
                ),
            },
            {
                "h2": (
                    "When the person who signs for it is the person who "
                    "uses it"
                ),
                "body": (
                    "Not every delivery point has a receiving function "
                    "behind it. Where there is no mailroom, no shipper "
                    "and nobody whose job the door is, the person who "
                    "signs was already halfway through something when the "
                    "buzzer went, and is the same person who will be at "
                    "the bench with it an hour later. That quietly "
                    "changes what a delivery span means to you. Somewhere "
                    "large, a parcel can sit indoors in a mail area until "
                    "someone wanders down for it. In a two-person setup, "
                    "if that one person is out at a supplier or gone for "
                    "the afternoon, the box stays where the driver left "
                    "it. Worth settling before the order goes in, then: "
                    "who is the backup receiver, and do they actually "
                    "know something is coming?"
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "The box sat in the sun on our step most of an "
                    "afternoon before anyone got to it. What should we do "
                    "with it?"
                ),
                "a": (
                    "Honestly, we cannot tell you anything useful about "
                    "what those hours did, and we are not going to guess. "
                    "What we would do is write down what happened while "
                    "it is fresh: roughly how long it was out, which way "
                    "the step faces, whether the carton felt warm or "
                    "looked deformed when it came inside. Then the "
                    "decision about whether it still suits your protocol "
                    "is yours, made against your own acceptance criteria "
                    "rather than against anything we have said."
                ),
            },
            {
                "q": (
                    "Our delivery point is out of town, toward Redcliff "
                    "or Dunmore. Does that change the timing?"
                ),
                "a": (
                    "The 10 to 15 day span is the same either way. The "
                    "difference is the very last step. A rural or "
                    "community box means the parcel can sit inside a "
                    "metal enclosure with the sun on it until somebody "
                    "drives out, and that drive often happens at the end "
                    "of the day rather than the middle of it. If there is "
                    "a staffed address in town willing to take it in and "
                    "keep it inside, naming that as the delivery point is "
                    "usually less trouble than writing careful "
                    "instructions for a rural route."
                ),
            },
            {
                "q": (
                    "Our lab shuts for a couple of weeks in August. Order "
                    "now or after?"
                ),
                "a": (
                    "After, unless you have somebody reliable receiving "
                    "while everyone is away. With a span of 10 to 15 "
                    "days, an order placed just before a shutdown has a "
                    "real chance of turning up at a locked building in "
                    "high summer, and then nobody knows where it spent "
                    "its afternoons. Placing it once people are back "
                    "costs you exactly the same span and removes that "
                    "whole question."
                ),
            },
        ],
    },
    {
        "slug": "grande-prairie",
        "market": "CA",
        "owner": "peptidesalberta.ca",
        "parent": "alberta",
        "name": "Grande Prairie",
        "short": "Grande Prairie",
        "cities": ["Grande Prairie"],
        "timezone": "Mountain Time",
        "title": "Research Peptides in Grande Prairie and the Peace",
        "meta_description": (
            "How to write a Peace Country site address into the checkout "
            "fields so a driver can find it, and why the last stretch is "
            "already inside the quoted window."
        ),
        "h1": (
            "Ordering Research Peptides to Grande Prairie and the Peace "
            "Country"
        ),
        "intro": (
            "Most of what goes wrong with a delivery into the Peace "
            "Country is decided before the order is placed, in the "
            "shipping fields. Around Grande Prairie the receiving point "
            "is often a lease road or a plant gate rather than a numbered "
            "street, and the run out to it is long enough that a second "
            "attempt costs days rather than hours. So this page runs in "
            "the order the problems actually turn up. Two things to "
            "settle first: everything catalogued here is stocked for "
            "bench work in a research setting, and it is not for "
            "administration to people or to animals. Nothing below should "
            "be read as direction for use in a living subject."
        ),
        "sections": [
            {
                "h2": (
                    "Write the receiving point the way a driver would "
                    "find it"
                ),
                "body": (
                    "A street address gives a driver a number, a name and "
                    "the assumption of a signed road. A site address does "
                    "none of that. Around Grande Prairie the receiving "
                    "point is frequently a gas plant, a mill site, a camp "
                    "or field office, a seed-cleaning or agronomy "
                    "operation, or a sample intake bench attached to a "
                    "plant, and plenty of those sit on a range road or a "
                    "lease road outside the city limits where the "
                    "location is identified by land description rather "
                    "than a civic number. Everything the driver has to "
                    "work with comes out of the shipping fields on your "
                    "order. Nobody reconstructs it later, and nobody "
                    "phones you to ask. So if your receiving point is a "
                    "site, enter it as one: the legal land description or "
                    "site identifier if that is how the place is "
                    "genuinely located, the road you turn off and which "
                    "direction you travel from there, the operator or "
                    "facility name that appears on the gate, and the name "
                    "and mobile number of whoever signs. A loose entry is "
                    "rarely refused outright. It is simply attempted, and "
                    "on a run this long an attempt that fails is measured "
                    "in days. Getting it right costs nothing and happens "
                    "at the keyboard."
                ),
            },
            {
                "h2": (
                    "The long final leg is already inside the 10 to 15 "
                    "days"
                ),
                "body": (
                    "Scheduled runs into this part of the province are "
                    "sparse, and that changes the arithmetic more than "
                    "raw distance does. A parcel that misses a departure "
                    "is not waiting an hour for the next one. It waits "
                    "for the next run, and some days there is not another "
                    "one. That is why the 10 to 15 days we quote is a "
                    "range rather than a named day. It was not set for "
                    "easier destinations and then stretched when the "
                    "Peace Country came up. The long final leg was built "
                    "into the figure from the start, so a delivery out to "
                    "a lease road is the thing the number already "
                    "describes, not an exception to it. It is also the "
                    "only timing we quote, on every order and for every "
                    "destination, so the range on this page is the range "
                    "that governs yours. If a project milestone governs "
                    "when the material has to be on the shelf, place the "
                    "order early enough that the full fifteen days can "
                    "elapse in front of it and still leave you room."
                ),
            },
            {
                "h2": "Deep winter and spring breakup on the last stretch",
                "body": (
                    "Two stretches of the year change how a run to a "
                    "rural receiving point behaves. In deep winter, "
                    "storms and drifting can slow or close routes into "
                    "the region for a day at a time, and a delay of that "
                    "size does not get made up later in the trip. In "
                    "spring, when the frost comes out of the ground and "
                    "the secondary roads go soft, moving weight out to a "
                    "site is slower work for a few weeks. Neither of "
                    "those moves the figure we quote. The range reads the "
                    "same in January as it does in July. What the season "
                    "decides is where inside that range a given order "
                    "tends to fall: nearer the front of it in a quiet "
                    "stretch, nearer the back of it when the weather is "
                    "doing the scheduling. One physical consequence is "
                    "worth knowing about. A parcel crossing the region in "
                    "January may spend part of its trip in unheated "
                    "depots and trailers, and nothing about how it is "
                    "packed changes that. If exposure is a variable in "
                    "your protocol, plan around the possibility rather "
                    "than assume against it."
                ),
            },
            {
                "h2": "Somebody has to be at the gate when the driver is",
                "body": (
                    "A remote receiving point is only as useful as its "
                    "coverage. Gate hours belong in the shipping notes, "
                    "and so does anything unusual about them: a camp "
                    "office attended part of the week, a plant gate that "
                    "rolls to a call box after shift, a field office that "
                    "is effectively empty in a busy season because "
                    "everyone is out on the ground. A driver at a locked "
                    "gate at 16:30 on a Friday with no number to call is "
                    "a wasted run on a route that does not get many. Two "
                    "names beat one. A primary contact who is expecting "
                    "the parcel, plus a second who can be reached when "
                    "the first is on days off or out of coverage, is "
                    "usually the difference between a delivery and a "
                    "return trip. None of that coverage comes from us. We "
                    "keep nobody in Grande Prairie and nobody anywhere in "
                    "the Peace Country, and we hold no office, no storage "
                    "and no bench in the region, so there is no local "
                    "person to meet a driver, hold a parcel or sort out a "
                    "gate problem on your behalf. Receiving sits entirely "
                    "at your end, which is exactly why it pays to arrange "
                    "it before the order goes in."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "Our intake sits on a lease road with no civic "
                    "number. How do I put that into the address fields?"
                ),
                "a": (
                    "Describe it the way you would describe it to a "
                    "driver over the phone, not the way a form expects a "
                    "street address to look. Legal land description or "
                    "site identifier, the road and the turn-off with a "
                    "direction of travel, the operator or facility name "
                    "on the gate, a receiving contact with a mobile "
                    "number, and the hours the gate is attended. "
                    "Industrial and rural receiving points are ordinary "
                    "in this part of the province. The deliveries that "
                    "fail are the ones described loosely."
                ),
            },
            {
                "q": (
                    "Can I get a firm delivery date to slot into our "
                    "project schedule?"
                ),
                "a": (
                    "No. We quote a 10 to 15 day range and do not commit "
                    "to a specific day, for this region or any other. The "
                    "final leg out here carries real variability, so a "
                    "named date would be a guess wearing the clothes of a "
                    "commitment. For scheduling, plan against the "
                    "fifteenth day and place the order far enough ahead "
                    "of your milestone that the whole range fits in front "
                    "of it."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------
    # BRITISH COLUMBIA CITY PAGE — smashfatbiolabs.ca only.
    #
    # One, not five. Drafts for Surrey, Burnaby, Victoria and Kelowna were
    # written and rejected: an audit claim-mapped them and found the same
    # four arguments (order against the window; be present for it; name a
    # person not a department; central receiving adds an internal leg)
    # recurring on every page, and three of the five reproduced Alberta
    # framings. City logistics pages have a finite argument space, and
    # eleven of them across one network is past what can be genuinely
    # differentiated. Vancouver earns its page because sustained coastal
    # rain does something to a carton that no prairie page describes.
    # The other centres are served by the British Columbia page.
    # ------------------------------------------------------------------
    {
        "slug": "vancouver",
        "market": "CA",
        "owner": "smashfatbiolabs.ca",
        "parent": "british-columbia",
        "name": "Vancouver",
        "short": "Vancouver",
        "cities": ["Vancouver"],
        "timezone": "Pacific Time",
        "title": "Research Peptides in Vancouver, BC | Receiving Notes",
        "meta_description": (
            "Notes for researchers ordering to a Vancouver address, where "
            "rain, downtown loading zones and an early-closing receiving "
            "desk decide when a box lands."
        ),
        "h1": "Research Peptides in Vancouver, British Columbia",
        "intro": (
            "Rain is the local variable. Not weather that arrives and "
            "passes, but days of it in a row off the water — fine enough "
            "that nobody calls it a storm, steady enough to keep a "
            "doorstep dark from morning until dusk. Cardboard left out in "
            "that is a different problem from cardboard left out in cold. "
            "Everything below is about the last hundred metres of a "
            "Vancouver delivery: the step, the lobby, the lane door, the "
            "desk that shuts before you do. These are laboratory "
            "reference materials sold for research use only, never for "
            "use in humans or animals."
        ),
        "sections": [
            {
                "h2": "Rain gets to the box before you do",
                "body": (
                    "The failure mode on the coast is not a frozen "
                    "parcel. It is a soft one. Corrugate wicks. An hour "
                    "of drizzle darkens the bottom flap, an afternoon of "
                    "it takes the stiffness out of the corners, and a box "
                    "that has gone soft is a box that tears when you lift "
                    "it by the wrong edge. Most of that happens after the "
                    "driver has gone. So choose a drop point with "
                    "something over it. A recessed entry, an awning, a "
                    "covered stair, the alcove behind the glass — "
                    "anything that is not open sky. Write it into the "
                    "address notes in plain words: leave under the "
                    "awning, left side. If the only unattended spot is "
                    "open to the weather and the sky looks committed, "
                    "don't gamble on it; ask for a signature and let the "
                    "box come back rather than sit. When one does arrive "
                    "wet, get it off the ground and out of the wet before "
                    "you open it. Cutting into a saturated lid drags "
                    "water and street grit inward, and tape on damp liner "
                    "peels rather than releases."
                ),
            },
            {
                "h2": "Downtown, the driver stops at the lobby",
                "body": (
                    "On the peninsula the geometry runs against the "
                    "courier. Loading zones are short and usually "
                    "occupied. Curb space thins out as the afternoon "
                    "fills up. One-way blocks and separated bike lanes "
                    "narrow the options further, and a driver who finds a "
                    "legal stop is often most of a block from your door "
                    "with a hand cart and several stops in the same "
                    "tower. That driver is not reaching your floor. "
                    "Fobbed elevators, secured floors and a concierge who "
                    "signs on behalf of the building mean the parcel ends "
                    "at a desk in the lobby or a room off P1 — and the "
                    "trip from desk to bench is yours. Plan for it. "
                    "Somebody has to know the box exists and go collect "
                    "it. Two things shorten that trip: a phone number a "
                    "person actually answers that day, and a named "
                    "receiving contact on the label instead of a "
                    "department. Write the real municipality too. Plenty "
                    "of addresses people call Vancouver sort as Burnaby, "
                    "Richmond or North Vancouver, and the courier reads "
                    "the postal code, not the habit."
                ),
            },
            {
                "h2": "A unit, not a floor",
                "body": (
                    "Much of the bench space in this city was never in a "
                    "tower. It is a converted warehouse with a loading "
                    "door somebody bricked up years ago, a strata unit "
                    "sitting over a ground-floor retail bay, a light- "
                    "industrial block near the Flats or off Main with six "
                    "tenants and one buzzer panel. Good rooms. Awkward "
                    "addresses. What changes at the door: no concierge, "
                    "no mailroom, so no default person to receive. The "
                    "street entrance is glass, locked and unlabelled. The "
                    "unit number is on the door inside, not on the "
                    "facade. The way in is around the side or off the "
                    "lane. The buzzer still lists a tenant who left two "
                    "leases ago. The fixes are small ones. Put a current "
                    "name on the buzzer and use that same name on the "
                    "order. Say which entrance in the notes — lane door, "
                    "north side, up the ramp. Decide in advance who signs "
                    "when the person who ordered is out, because in a "
                    "six-unit building the driver's fallback is a "
                    "neighbour or a notice card, and a notice card costs "
                    "you a day."
                ),
            },
        ],
        "faqs": [
            {
                "q": (
                    "The parcel sat out in the rain before I got to it. "
                    "What should I do with it?"
                ),
                "a": (
                    "Bring it inside, set it on a dry surface off the "
                    "floor, and let the outside dry before you cut "
                    "anything. Opening a saturated box pulls water and "
                    "street grit inward, and wet tape lifts the liner "
                    "instead of releasing cleanly. If the outer packaging "
                    "has actually failed — split corner, sagging base, a "
                    "lid you can push a thumb through — photograph it "
                    "before you go further, then send us the order number "
                    "with those photos and we will take it from there."
                ),
            },
            {
                "q": (
                    "Our building makes couriers book the loading bay and "
                    "hand everything to concierge. Does that cause a "
                    "problem?"
                ),
                "a": (
                    "No. That is ordinary downtown and the delivering "
                    "carrier works with it every day. Put the instruction "
                    "where a driver will read it — concierge accepts, or "
                    "dock booking required — along with a number someone "
                    "answers. Expect the signature to be the building's "
                    "rather than yours, and expect the box to wait at the "
                    "desk until you go down for it. The one thing we "
                    "cannot do is book the slot; that arrangement sits "
                    "between your building and the carrier, and it is "
                    "usually a single phone call from your side."
                ),
            },
            {
                "q": (
                    "How should I write the address for a unit in a "
                    "mixed-use building?"
                ),
                "a": (
                    "Two short lines beat one long one. Put the unit "
                    "first, hyphenated to the civic number the way strata "
                    "addresses are written here, then the street. Use the "
                    "second line for what a driver needs at street level: "
                    "which entrance, and the name showing on the buzzer. "
                    "Keep each to a few words, since long labels get "
                    "truncated. And use the municipality the postal code "
                    "belongs to rather than the one people say out loud — "
                    "a unit written as Vancouver that is really in "
                    "Burnaby adds a handling step it does not need."
                ),
            },
        ],
    },
    # ------------------------------------------------------------------
    # UNITED STATES — 12 states, served by the .com storefronts
    # ------------------------------------------------------------------
    {
        "slug": "california",
        "market": "US",
        "owner": "smashfatbiolabs.com",
        "name": "California",
        "short": "CA",
        "cities": ["Los Angeles", "San Diego", "San Francisco", "San Jose", "Sacramento", "Irvine"],
        "title": "California Research Peptides | Research Use Only",
        "timezone": "Pacific Time",
        "meta_description": (
            "Research compounds for California labs. Statewide coverage, USD "
            "pricing, CBP customs notes, 10 to 15 day shipping window. Research "
            "use only."
        ),
        "h1": "California Research Compounds, San Diego to the Bay",
        "intro": (
            "California carries more distinct research clusters than any other "
            "state, spread from San Diego up through the Bay Area with a long "
            "inland stretch in between. Those clusters have little in common "
            "except that summer inland heat affects all of them. Our catalogue "
            "is supplied for laboratory research use only."
        ),
        "sections": [
            {
                "h2": "Coverage from San Diego to the Bay",
                "body": (
                    "San Diego, the Los Angeles and Orange County area, the San "
                    "Francisco Bay region and Sacramento account for most "
                    "California orders. The Central Valley and the far north "
                    "are served on the same terms. There is no part of the "
                    "state that gets a different catalogue or a different price "
                    "list."
                ),
            },
            {
                "h2": "Pacific Time and order cut-offs",
                "body": (
                    "California sits at the western end of the US day. Our "
                    "order queue runs on a daily cycle, so a California order "
                    "placed in the afternoon is competing with a batch that has "
                    "been filling since the eastern morning. Placing an order "
                    "earlier in the Pacific day gets it into that cycle rather "
                    "than the following one."
                ),
            },
            {
                "h2": "Summer heat inland",
                "body": (
                    "Coastal California is mild most of the year. Inland is "
                    "not. A parcel sitting on a sunny doorstep or in a parked "
                    "vehicle through a Central Valley afternoon is the case "
                    "worth avoiding. Compounds ship lyophilised, which is the "
                    "form that copes best with transit, but the sensible step "
                    "is to bring the box indoors quickly and store vials as the "
                    "label states."
                ),
            },
            {
                "h2": "What Customs and Border Protection may do",
                "body": (
                    "A parcel arriving in the United States can be held, opened "
                    "or examined at the discretion of US Customs and Border "
                    "Protection. Nobody selling goods gets to speed that up, "
                    "and we do not pretend otherwise. Where an examination "
                    "happens, days are added on top of our 10 to 15 day "
                    "window. Whether you may lawfully hold what you have "
                    "ordered is a question only you can answer."
                ),
            },
        ],
        "faqs": [
            {
                "q": "What currency do California prices show in?",
                "a": (
                    "US dollars. Every .com storefront in the network displays "
                    "USD."
                ),
            },
            {
                "q": "Do you have a California facility?",
                "a": (
                    "No. We serve researchers in California and hold no "
                    "premises, staff or laboratory in the state."
                ),
            },
            {
                "q": "Will heat ruin a summer delivery?",
                "a": (
                    "Material ships dry and sealed, which is the form that best "
                    "handles a transit swing. Bring the parcel indoors promptly "
                    "and store vials as labelled."
                ),
            },
            {
                "q": "Are these compounds for human use?",
                "a": (
                    "No. They are supplied for laboratory research only, and "
                    "not for human or veterinary use."
                ),
            },
        ],
    },
    {
        "slug": "texas",
        "market": "US",
        "owner": "smashfatbiolabs.com",
        "name": "Texas",
        "short": "TX",
        "cities": ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "College Station"],
        "timezone": "Central Time",
        "title": "Texas Research Peptides | Laboratory Use Only",
        "meta_description": (
            "Research peptide supply across Texas. Houston, Dallas, Austin and "
            "San Antonio. Heat handling notes, USD pricing, 10 to 15 day "
            "window. Research use only."
        ),
        "h1": "Texas Research Peptide Supply",
        "intro": (
            "Texas is a state of large, widely separated metros, each with its "
            "own research character, and a climate that puts real heat on a "
            "parcel for a good part of the year. Volume here is spread rather "
            "than concentrated. Every compound listed is for laboratory "
            "research only."
        ),
        "sections": [
            {
                "h2": "Four metros and a long tail",
                "body": (
                    "Houston, the Dallas and Fort Worth area, Austin and San "
                    "Antonio take most Texas orders, with College Station, "
                    "Lubbock and El Paso adding steady volume. The distances "
                    "between them are national-scale, but the delivery terms "
                    "and the window do not change from one to another."
                ),
            },
            {
                "h2": "Heat is the handling problem here",
                "body": (
                    "For much of the year a Texas doorstep is hotter than "
                    "anywhere a vial should sit. Dry lyophilised material is "
                    "the most transit-tolerant form these compounds come in, "
                    "which is why they ship that way, but the useful step is at "
                    "your end. Collect the parcel promptly, keep it out of a "
                    "parked vehicle, and move vials to the labelled storage "
                    "condition."
                ),
            },
            {
                "h2": "Central Time",
                "body": (
                    "Most of Texas keeps Central Time, with the far west corner "
                    "of the state on Mountain Time. Our processing runs daily "
                    "rather than to a clock minute, so the practical point is "
                    "simply that an order placed during the Texas working day "
                    "lands in that day's batch."
                ),
            },
            {
                "h2": "Pricing shown in US dollars",
                "body": (
                    "Texas buyers see USD throughout. The price against each "
                    "compound is per vial, and several items are offered in more "
                    "than one vial size, so check the size on the line before "
                    "comparing two numbers. The same catalogue and the same "
                    "list apply to every US storefront in the network."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How long does a Texas order take?",
                "a": (
                    "Orders move on a 10 to 15 day window. Customs inspection "
                    "can extend it and we do not promise a fixed date."
                ),
            },
            {
                "q": "Should I worry about summer transit?",
                "a": (
                    "Compounds ship lyophilised and sealed. The step that "
                    "matters is retrieving the parcel promptly and storing "
                    "vials as the label states."
                ),
            },
            {
                "q": "Do you have a Texas warehouse?",
                "a": (
                    "No. We serve researchers in Texas and hold no facility in "
                    "the state."
                ),
            },
        ],
    },
    {
        "slug": "new-york",
        "market": "US",
        "owner": "smashfatbiolabs.com",
        "name": "New York",
        "short": "NY",
        "cities": ["New York City", "Buffalo", "Rochester", "Albany", "Syracuse", "Ithaca"],
        "timezone": "Eastern Time",
        "title": "New York Research Peptides | Research Use Only",
        "meta_description": (
            "Research compounds for New York State. City and upstate coverage, "
            "documentation notes, USD pricing, 10 to 15 day window. Not for human or "
            "veterinary use."
        ),
        "h1": "Research Compounds for New York",
        "intro": (
            "New York splits neatly into two supply situations: a dense "
            "metropolitan area where the difficulty is the building, and an "
            "upstate corridor where it is the distance. Both are served on the "
            "same terms. Nothing in the catalogue is intended for human or "
            "veterinary use."
        ),
        "sections": [
            {
                "h2": "City and upstate",
                "body": (
                    "New York City and the surrounding counties carry the "
                    "largest share of state orders. Upstate volume runs along "
                    "the corridor through Albany, Syracuse, Rochester and "
                    "Buffalo, with Ithaca and the Southern Tier adding more. "
                    "The catalogue and the window are identical in both halves "
                    "of the state."
                ),
            },
            {
                "h2": "Addresses in dense buildings",
                "body": (
                    "In the city, most delivery problems are last-hundred-metre "
                    "problems. A tower, a shared floor or a mailroom needs a "
                    "suite number and a recipient name that matches the "
                    "building's directory. Without one, a parcel can reach the "
                    "right street and then sit. Include a phone number the "
                    "carrier can call and note any reception hours at checkout."
                ),
            },
            {
                "h2": "Working on Eastern Time",
                "body": (
                    "New York runs on Eastern Time, which puts it at the front "
                    "of the US working day. Our order batch and support replies "
                    "run on a daily cycle. An order placed in the New York "
                    "morning is comfortably inside that cycle; one placed late "
                    "at night is not."
                ),
            },
            {
                "h2": "Why no analytical paperwork accompanies an order",
                "body": (
                    "A complete analytical document would name the "
                    "compound, the batch, the method and the figure that "
                    "method returned. None is issued here, for any item, "
                    "and no figure is published to stand behind. That is "
                    "the position rather than an omission: work that "
                    "depends on confirmed identity or content needs its "
                    "own determination, made on its own instruments."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Can you deliver to a Manhattan office building?",
                "a": (
                    "Yes, with a suite number, a recipient name the building "
                    "recognises and a reachable phone number."
                ),
            },
            {
                "q": "Is upstate delivery slower?",
                "a": (
                    "The window is 10 to 15 days statewide. Upstate addresses "
                    "may land later within it."
                ),
            },
            {
                "q": "Is there a purity figure for the catalogue?",
                "a": (
                    "None is published. No analytical work is carried out "
                    "here and no figure is quoted, so there is nothing to "
                    "cite in a specification."
                ),
            },
        ],
    },
    {
        "slug": "florida",
        "market": "US",
        "owner": "smashfatbiolabs.com",
        "name": "Florida",
        "short": "FL",
        "cities": ["Miami", "Orlando", "Tampa", "Jacksonville", "Gainesville", "Fort Lauderdale"],
        "timezone": "Eastern Time",
        "title": "Florida Research Peptides | Lab Supply, USD",
        "meta_description": (
            "Research peptide supply for Florida. Heat and humidity handling, "
            "storm-season buffers, USD pricing, 10 to 15 day window. Research "
            "use only."
        ),
        "h1": "Florida Research Peptides and Warm-Climate Handling",
        "intro": (
            "Florida asks two questions of a shipment that most states do not: "
            "what happens in sustained heat, and what happens when a storm "
            "closes a route. Both are worth planning around. The compounds we "
            "list are supplied for laboratory research and nothing else."
        ),
        "sections": [
            {
                "h2": "Heat and humidity, most of the year",
                "body": (
                    "Warm, humid conditions are the Florida baseline rather "
                    "than a summer exception. Compounds ship lyophilised and "
                    "sealed, which is the form least bothered by that. The "
                    "handling that matters happens after delivery: retrieve the "
                    "parcel quickly, do not leave it in a vehicle, and move "
                    "vials into the labelled storage condition in a room that "
                    "stays dry."
                ),
            },
            {
                "h2": "Where we deliver",
                "body": (
                    "South Florida, the Orlando area, Tampa Bay and "
                    "Jacksonville carry most state volume, with Gainesville and "
                    "the panhandle adding more. Coastal and inland addresses "
                    "are handled identically. As elsewhere, a full address with "
                    "a unit number and a phone number is what keeps a parcel "
                    "moving."
                ),
            },
            {
                "h2": "Storm season and route closures",
                "body": (
                    "Between roughly midsummer and late autumn, weather closes "
                    "routes in this state more often than in most. Our window "
                    "stays at 10 to 15 days, but a closed route is a delay no "
                    "supplier can shorten. If material is needed for scheduled "
                    "work during that stretch, order earlier rather than "
                    "against the end of the window."
                ),
            },
            {
                "h2": "Customs on inbound parcels",
                "body": (
                    "Shipments entering the United States may be subject to "
                    "inspection by US Customs and Border Protection. We do not "
                    "claim to pre-clear anything and we make no statement about "
                    "where goods move from. The buyer is responsible for "
                    "confirming that they may lawfully receive and hold the "
                    "material."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Does humidity affect a sealed vial?",
                "a": (
                    "A sealed lyophilised vial is not open to room air. Store "
                    "it as labelled and keep it out of direct light once the "
                    "parcel is opened."
                ),
            },
            {
                "q": "What happens if a storm delays my order?",
                "a": (
                    "The window is 10 to 15 days and a route closure can push "
                    "past it. Contact support with your order number and we "
                    "will share what we can see."
                ),
            },
            {
                "q": "Are Florida prices in USD?",
                "a": "Yes. All .com storefronts show US dollars.",
            },
        ],
    },
    {
        "slug": "massachusetts",
        "market": "US",
        "owner": "smash-fat.com",
        "name": "Massachusetts",
        "short": "MA",
        "cities": ["Boston", "Cambridge", "Worcester", "Springfield", "Lowell", "Amherst"],
        "timezone": "Eastern Time",
        "title": "Massachusetts Research Peptides | Research Use Only",
        "meta_description": (
            "Research compounds for Massachusetts. Dense corridor coverage, "
            "purity documentation notes, USD pricing, 10 to 15 day window. Lab "
            "use only."
        ),
        "h1": "Research Peptide Supply in Massachusetts",
        "intro": (
            "Massachusetts packs a dense research corridor into a small "
            "geographic area, which makes it one of the more document-focused "
            "markets we serve. Buyers here ask about batches and methods more "
            "often than they ask about shipping. All material is supplied for "
            "laboratory research only."
        ),
        "sections": [
            {
                "h2": (
                "What a purity figure would tell you, and why none is "
                "quoted"
            ),
                "body": (
                    "A purity figure describes composition on one batch, "
                    "measured by one named method. It says nothing about "
                    "biological activity. It is worth understanding "
                    "because it is quoted so freely elsewhere — and worth "
                    "saying plainly that none is quoted here, for any "
                    "item, because no such measurement has been made. A "
                    "number with no method and no batch beside it would "
                    "be incomplete anyway."
                ),
            },
            {
                "h2": "A short corridor with a lot on it",
                "body": (
                    "Boston and Cambridge take the bulk of state volume, with "
                    "the Route 128 belt, Worcester, Lowell, Springfield and the "
                    "Amherst area following. Nothing in the state is far by "
                    "national standards. The practical difference between "
                    "addresses here is building access rather than distance."
                ),
            },
            {
                "h2": "Winter transit",
                "body": (
                    "New England winters put parcels through freezing "
                    "conditions and occasional storm delays. Dry lyophilised "
                    "material handles cold better than it handles sustained "
                    "heat. Let a cold sealed vial come up to room temperature "
                    "before opening it, so moisture does not condense on the "
                    "stopper, then store it as the label states."
                ),
            },
            {
                "h2": "When messages get read",
                "body": (
                    "Massachusetts runs on Eastern Time. Our order queue is "
                    "processed daily, so an order or a support message sent "
                    "during the local working day is handled in that cycle "
                    "rather than the following one."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Is batch paperwork available before ordering?",
                "a": (
                    "There is none to see. No batch-level documentation "
                    "is generated for any catalogue item, so nothing can "
                    "be sent ahead of an order or after one."
                ),
            },
            {
                "q": "Do you supply institutions?",
                "a": (
                    "We ship to the address given at checkout. We have no "
                    "affiliation with any institution and claim none."
                ),
            },
            {
                "q": "How long is delivery?",
                "a": (
                    "A 10 to 15 day window, which customs inspection can "
                    "extend."
                ),
            },
            {
                "q": "Are these for human use?",
                "a": (
                    "No. Research use only, not for human or veterinary use."
                ),
            },
        ],
    },
    {
        "slug": "illinois",
        "market": "US",
        "owner": "smash-fat.com",
        "name": "Illinois",
        "short": "IL",
        "cities": ["Chicago", "Evanston", "Urbana", "Peoria", "Rockford", "Springfield"],
        "timezone": "Central Time",
        "title": "Illinois Research Peptides | Laboratory Supply",
        "meta_description": (
            "Research compound supply for Illinois. Chicago and downstate "
            "coverage, seasonal handling notes, USD pricing, 10 to 15 day "
            "window. Research use only."
        ),
        "h1": "Illinois Research Compounds, Chicago and Downstate",
        "intro": (
            "Illinois runs a hard seasonal swing, with genuine winter cold and "
            "genuine summer heat inside the same calendar year. Chicago "
            "dominates the state's order volume while downstate centres add a "
            "steady share. We supply the state for laboratory research use "
            "only."
        ),
        "sections": [
            {
                "h2": "Two seasons, two different risks",
                "body": (
                    "A January parcel meets freezing conditions; a July parcel "
                    "meets heat. Of the two, sustained heat is the one worth "
                    "more attention for dry material. In winter, let a cold "
                    "sealed vial equalise before opening. In summer, do not "
                    "leave the box on a step or in a car. Either way the "
                    "storage condition on the label is where the vial belongs."
                ),
            },
            {
                "h2": "Central Time and the daily cycle",
                "body": (
                    "Illinois keeps Central Time, an hour behind the eastern "
                    "seaboard. Our order batch runs once a day, so an order "
                    "placed during the Illinois working day is inside that "
                    "batch. Late evening orders roll into the following cycle, "
                    "as do support messages sent after hours."
                ),
            },
            {
                "h2": "Chicago and downstate",
                "body": (
                    "The Chicago metropolitan area, including Evanston and the "
                    "collar counties, carries most Illinois volume. Urbana and "
                    "the central part of the state, along with Peoria, Rockford "
                    "and Springfield, make up the rest. Every address is served "
                    "on the same window and the same price list."
                ),
            },
            {
                "h2": "A short pre-order checklist",
                "body": (
                    "Confirm the compound name and the vial size, since several "
                    "items ship in more than one size and the price is per "
                    "vial. Confirm the delivery address, unit number and "
                    "phone. Then confirm that you may lawfully receive and hold "
                    "the material where you are, which is the buyer's "
                    "responsibility."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Do you ship to downstate Illinois?",
                "a": (
                    "Yes, on the same 10 to 15 day window as the Chicago area."
                ),
            },
            {
                "q": "What form do compounds arrive in?",
                "a": (
                    "Lyophilised powder in a sealed vial. We do not supply "
                    "diluents or administration guidance."
                ),
            },
            {
                "q": "Is there an Illinois price list?",
                "a": (
                    "No. One USD catalogue applies to every US storefront in "
                    "the network."
                ),
            },
        ],
    },
    {
        "slug": "pennsylvania",
        "market": "US",
        "owner": "smash-fat.com",
        "name": "Pennsylvania",
        "short": "PA",
        "cities": ["Philadelphia", "Pittsburgh", "Allentown", "Harrisburg", "State College", "Hershey"],
        "timezone": "Eastern Time",
        "title": "Pennsylvania Research Peptides | Research Use Only",
        "meta_description": (
            "Research peptides for Pennsylvania labs. Philadelphia and "
            "Pittsburgh coverage, storage guidance, USD pricing, 10 to 15 day "
            "window. Not for human use."
        ),
        "h1": "Pennsylvania Research Peptides, Philadelphia to Pittsburgh",
        "intro": (
            "Pennsylvania has two anchor cities at opposite ends of the state "
            "and a spread of smaller research centres between them. That shape "
            "means no single hub covers the market. Compounds listed here are "
            "supplied for laboratory research and are not for human or "
            "veterinary use."
        ),
        "sections": [
            {
                "h2": "East and west, plus everything between",
                "body": (
                    "Philadelphia and its suburbs anchor the eastern end, "
                    "Pittsburgh the western. Allentown, Harrisburg, State "
                    "College, Hershey and Scranton fill in the middle and the "
                    "northeast. Because the state is wide, a parcel crossing it "
                    "adds road time, but the 10 to 15 day window covers the "
                    "whole state without variation."
                ),
            },
            {
                "h2": "The clock we work to",
                "body": (
                    "Pennsylvania keeps Eastern Time. Our daily processing "
                    "cycle means an order or message sent during the local "
                    "working day is handled that day, while anything sent "
                    "overnight is picked up on the next cycle. There is no "
                    "separate regional support line."
                ),
            },
            {
                "h2": "Storing vials after delivery",
                "body": (
                    "Compounds arrive lyophilised and sealed. Move them to the "
                    "storage condition printed on the label as soon as you open "
                    "the parcel, keep them out of direct light, and avoid "
                    "repeated warming and cooling. If a vial arrived cold, "
                    "allow it to reach room temperature while still sealed "
                    "before opening."
                ),
            },
            {
                "h2": "The terms every order carries",
                "body": (
                    "Checkout requires an acknowledgement that the purchase is "
                    "for laboratory research use only. We publish no guidance "
                    "on use in a living subject and make no medical or outcome "
                    "claims of any kind. Meeting the rules that apply where you "
                    "are is the buyer's responsibility, not ours."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Does a Pittsburgh order take longer than a Philadelphia one?",
                "a": (
                    "Both use the same 10 to 15 day window. Where inside it a "
                    "parcel lands varies."
                ),
            },
            {
                "q": "How should vials be stored on arrival?",
                "a": (
                    "As printed on the label, out of direct light, without "
                    "repeated warming and cooling cycles."
                ),
            },
            {
                "q": "What am I agreeing to at checkout?",
                "a": (
                    "That the material is for laboratory research use only and "
                    "not for human or veterinary use."
                ),
            },
        ],
    },
    {
        "slug": "washington",
        "market": "US",
        "owner": "smash-fat.com",
        "name": "Washington",
        "short": "WA",
        "cities": ["Seattle", "Bellevue", "Spokane", "Tacoma", "Pullman", "Vancouver"],
        "timezone": "Pacific Time",
        "title": "Washington State Research Peptides | Lab Use Only",
        "meta_description": (
            "Research compound supply for Washington State. Puget Sound and "
            "eastern coverage, USD pricing, 10 to 15 day window. Research use "
            "only."
        ),
        "h1": "Washington State Research Supply",
        "intro": (
            "Washington divides at the Cascades into a damp western side and a "
            "dry eastern one, and the two behave differently for anything left "
            "sitting outside. Puget Sound carries most of the state's research "
            "volume. Everything we list is supplied for laboratory research "
            "only."
        ),
        "sections": [
            {
                "h2": "Wet west, dry east",
                "body": (
                    "On the western side, rain is the common condition and a "
                    "damp outer box is the usual arrival state. Check that the "
                    "packaging is dry before opening it. East of the Cascades, "
                    "summer runs hot and winter runs cold, so the swing is "
                    "wider. Sealed lyophilised vials handle both, provided they "
                    "reach the labelled storage condition promptly."
                ),
            },
            {
                "h2": "Pacific Time",
                "body": (
                    "Washington keeps Pacific Time, which means the local "
                    "working day starts after the eastern one is well under "
                    "way. Our order batch runs daily. Sending an order or a "
                    "question earlier in the Pacific morning puts it in that "
                    "day's cycle."
                ),
            },
            {
                "h2": "Coverage across the state",
                "body": (
                    "Seattle, Bellevue and the wider Puget Sound area take most "
                    "orders, with Tacoma and Olympia close behind. Spokane and "
                    "Pullman cover the east, and the Vancouver area in the "
                    "southwest is served the same way. Every address gets the "
                    "same catalogue and the same window."
                ),
            },
            {
                "h2": "Planning a single consolidated order",
                "body": (
                    "If you need several compounds over the coming weeks, "
                    "ordering them in one parcel is usually simpler than "
                    "staging them. One shipment means one window, one customs "
                    "step and one delivery. Check vial sizes line by line "
                    "first, since sizes differ between compounds and pricing is "
                    "per vial."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Does rain affect a delivery?",
                "a": (
                    "Check that the outer packaging is dry before opening it. "
                    "The vials inside are sealed."
                ),
            },
            {
                "q": "Do you deliver to eastern Washington?",
                "a": (
                    "Yes, on the same 10 to 15 day window used statewide."
                ),
            },
            {
                "q": "Can I combine compounds in one order?",
                "a": (
                    "Yes. One parcel means one window and one customs step."
                ),
            },
        ],
    },
    {
        "slug": "georgia",
        "market": "US",
        "owner": "where-do-i-get-peptides.com",
        "name": "Georgia",
        "short": "GA",
        "cities": ["Atlanta", "Athens", "Savannah", "Augusta", "Macon", "Columbus"],
        "timezone": "Eastern Time",
        "title": "Georgia Research Peptides | Research Use Only",
        "meta_description": (
            "Research peptides for Georgia labs. Atlanta and statewide "
            "coverage, humidity handling, CBP notes, USD pricing, 10 to 15 day "
            "window."
        ),
        "h1": "Georgia Research Peptides and Humid-Climate Notes",
        "intro": (
            "Georgia's order volume clusters heavily around one metro area, "
            "with a spread of smaller centres across the rest of the state. "
            "Warm, humid conditions run for most of the year here, which "
            "changes what happens to a parcel left outside. Our catalogue is "
            "for laboratory research use only."
        ),
        "sections": [
            {
                "h2": "Humidity and how it affects handling",
                "body": (
                    "Humid air matters less to a sealed vial than to an opened "
                    "one. Dry lyophilised powder is packed sealed and should be "
                    "kept that way until you use it. Once a parcel is open, "
                    "store vials in the condition on the label, in a dry room "
                    "rather than a garage or an outbuilding, and keep them out "
                    "of direct light."
                ),
            },
            {
                "h2": "Atlanta and beyond",
                "body": (
                    "The Atlanta metropolitan area carries most Georgia orders. "
                    "Athens, Augusta, Macon, Columbus and Savannah make up the "
                    "balance, along with the coastal and southern parts of the "
                    "state. There is no difference in catalogue, price or "
                    "window between them."
                ),
            },
            {
                "h2": "One daily cycle, Eastern Time",
                "body": (
                    "Georgia keeps Eastern Time. Our processing runs on a daily "
                    "cycle rather than a clock minute, so the practical guidance "
                    "is to place an order during the local working day if you "
                    "want it in that day's batch."
                ),
            },
            {
                "h2": "Inbound customs",
                "body": (
                    "Parcels entering the United States may be subject to "
                    "inspection by US Customs and Border Protection. Inspection "
                    "adds time that no supplier controls, and it can push a "
                    "parcel past the 10 to 15 day window. We make no claim "
                    "about where goods move from. The buyer is responsible for "
                    "their own compliance."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Where should vials be kept in a humid climate?",
                "a": (
                    "In the storage condition on the label, in a dry indoor "
                    "space, away from direct light."
                ),
            },
            {
                "q": "How long will a Georgia order take?",
                "a": (
                    "A 10 to 15 day window. Customs inspection can extend it."
                ),
            },
            {
                "q": "Do you have a Georgia location?",
                "a": (
                    "No. We serve researchers in Georgia and hold no premises "
                    "in the state."
                ),
            },
        ],
    },
    {
        "slug": "north-carolina",
        "market": "US",
        "owner": "where-do-i-get-peptides.com",
        "name": "North Carolina",
        "short": "NC",
        "cities": ["Raleigh", "Durham", "Charlotte", "Chapel Hill", "Winston-Salem", "Greensboro"],
        "timezone": "Eastern Time",
        "title": "North Carolina Research Peptides | Lab Use Only",
        "meta_description": (
            "Research compound supply for North Carolina. Triangle and "
            "Charlotte coverage, batch record notes, USD pricing, 10 to 15 day "
            "window. Research use only."
        ),
        "h1": "Research Compounds for North Carolina",
        "intro": (
            "North Carolina concentrates a great deal of its research activity "
            "in the Raleigh, Durham and Chapel Hill triangle, with a second "
            "centre of gravity around Charlotte. Buyers here tend to keep "
            "careful records, which the batch system supports. All material is "
            "supplied for laboratory research only."
        ),
        "sections": [
            {
                "h2": "The triangle, Charlotte and the Piedmont",
                "body": (
                    "Raleigh, Durham and Chapel Hill account for a large share "
                    "of state orders. Charlotte follows, then Greensboro, "
                    "Winston-Salem and the wider Piedmont, with the coastal "
                    "plain and the mountains behind them. The same window and "
                    "the same price list apply across all of it."
                ),
            },
            {
                "h2": "Batch identifiers and your own records",
                "body": (
                    "Each vial label carries a compound name, a vial size and a "
                    "batch identifier. The batch identifier is what ties a vial "
                    "to the purity document for that production run. Recording "
                    "it on receipt, alongside the arrival date, means a later "
                    "question about a specific vial can be answered from your "
                    "own file instead of by correspondence."
                ),
            },
            {
                "h2": "Summer humidity",
                "body": (
                    "Piedmont and coastal summers are warm and humid. A sealed "
                    "lyophilised vial is not exposed to room air, so the "
                    "important step is simply retrieving the parcel promptly "
                    "and moving vials to the labelled storage condition. A dry, "
                    "climate-stable indoor space is better than a garage."
                ),
            },
            {
                "h2": "Time zone and order timing",
                "body": (
                    "North Carolina keeps Eastern Time. Orders are processed in "
                    "a daily batch, so anything placed during the local working "
                    "day is handled in that cycle and anything sent overnight "
                    "waits for the next one."
                ),
            },
        ],
        "faqs": [
            {
                "q": "What is on the vial label?",
                "a": (
                    "The compound name, the vial size, a batch identifier and a "
                    "research-use-only statement."
                ),
            },
            {
                "q": "Can I request a purity document later?",
                "a": (
                    "Yes, if you have the batch identifier. That is the field "
                    "that links a vial to its document."
                ),
            },
            {
                "q": "Are prices in US dollars?",
                "a": "Yes. Every .com storefront shows USD.",
            },
        ],
    },
    {
        "slug": "ohio",
        "market": "US",
        "owner": "where-do-i-get-peptides.com",
        "name": "Ohio",
        "short": "OH",
        "cities": ["Columbus", "Cleveland", "Cincinnati", "Dayton", "Toledo", "Akron"],
        "timezone": "Eastern Time",
        "title": "Ohio Research Peptides | Research Use Only",
        "meta_description": (
            "Research peptide supply across Ohio. Columbus, Cleveland and "
            "Cincinnati coverage, winter handling notes, USD pricing, 10 to 15 "
            "day window."
        ),
        "h1": "Ohio Research Peptides Across Three Metro Areas",
        "intro": (
            "Ohio spreads its research work across three roughly equal metro "
            "areas rather than one dominant city, with a ring of smaller "
            "centres around them. Winters here are long enough to be worth "
            "planning for. Everything in the catalogue is supplied for "
            "laboratory research use only."
        ),
        "sections": [
            {
                "h2": "Three metros carrying similar weight",
                "body": (
                    "Columbus, Cleveland and Cincinnati each take a comparable "
                    "share of Ohio orders, with Dayton, Toledo and Akron "
                    "following. Because volume is spread rather than "
                    "concentrated, no part of the state is a "
                    "secondary destination. The window and the price list are "
                    "the same throughout."
                ),
            },
            {
                "h2": "Winter transit and the equalisation step",
                "body": (
                    "Ohio parcels spend real time below freezing between late "
                    "autumn and early spring. Dry lyophilised material tolerates "
                    "that well. The step people skip is at the other end: a "
                    "cold vial opened straight away can pick up condensation on "
                    "the stopper. Let it reach room temperature while still "
                    "sealed, then store it as the label states."
                ),
            },
            {
                "h2": "Eastern Time and the order queue",
                "body": (
                    "Ohio keeps Eastern Time. Our order queue is processed "
                    "daily, so orders and support messages sent during the "
                    "local working day are handled in that cycle."
                ),
            },
        ],
        "faqs": [
            {
                "q": "Is winter delivery a problem?",
                "a": (
                    "Dry lyophilised material handles cold transit. Let a cold "
                    "sealed vial reach room temperature before opening it."
                ),
            },
            {
                "q": "Which Ohio cities do you cover?",
                "a": (
                    "All of them. Columbus, Cleveland, Cincinnati, Dayton, "
                    "Toledo and Akron are the largest by volume."
                ),
            },
            {
                "q": "How long is the shipping window?",
                "a": (
                    "10 to 15 days, which customs inspection can extend."
                ),
            },
        ],
    },
    {
        "slug": "arizona",
        "market": "US",
        "owner": "where-do-i-get-peptides.com",
        "name": "Arizona",
        "short": "AZ",
        "cities": ["Phoenix", "Tucson", "Tempe", "Scottsdale", "Mesa", "Flagstaff"],
        "timezone": "Mountain Time (no seasonal change)",
        "title": "Arizona Research Peptides | Desert Climate Notes",
        "meta_description": (
            "Research compounds for Arizona labs. Desert heat handling, a clock "
            "that does not shift, USD pricing, 10 to 15 day window. Research "
            "use only."
        ),
        "h1": "Arizona Research Peptides and Desert Handling",
        "intro": (
            "Arizona presents the sharpest heat problem of any market we serve, "
            "and it also keeps a clock that does not move with the rest of the "
            "country. Both are worth knowing before you order. Compounds listed "
            "here are for laboratory research only, not for human or veterinary "
            "use."
        ),
        "sections": [
            {
                "h2": "Desert heat and the last few hours",
                "body": (
                    "The riskiest part of an Arizona delivery is not the "
                    "journey, it is the parcel sitting in full sun after the "
                    "carrier leaves. Sealed lyophilised material is the most "
                    "transit-tolerant form these compounds come in. Even so, there "
                    "is no reason to let a box bake all afternoon. Arrange for "
                    "someone to collect it, or use an address where a parcel "
                    "goes indoors on arrival."
                ),
            },
            {
                "h2": "A state clock that does not shift",
                "body": (
                    "Most of Arizona keeps the same time all year instead of "
                    "shifting seasonally, which means the state lines up with "
                    "Pacific Time for part of the year and Mountain Time for "
                    "the rest. Our order batch runs daily regardless. If you "
                    "are working to a cut-off, check the current offset rather "
                    "than relying on last season's."
                ),
            },
            {
                "h2": "Phoenix, Tucson and the north",
                "body": (
                    "Phoenix and the surrounding cities, including Tempe, Mesa "
                    "and Scottsdale, carry most Arizona orders. Tucson is "
                    "second, with Flagstaff and the northern part of the state "
                    "behind it. Flagstaff sits high enough that its winter is a "
                    "genuine one, so cold-weather handling applies there rather "
                    "than heat handling."
                ),
            },
            {
                "h2": "Customs and the shipping window",
                "body": (
                    "Orders move on a 10 to 15 day window. Inbound parcels may "
                    "be subject to inspection by US Customs and Border "
                    "Protection, which can add days beyond that. We do not "
                    "promise a specific arrival date and we make no claim about "
                    "where goods move from. Compliance with the rules that "
                    "apply to you is your responsibility."
                ),
            },
        ],
        "faqs": [
            {
                "q": "How do I avoid a parcel sitting in the sun?",
                "a": (
                    "Use an address where someone can bring the box indoors on "
                    "arrival, and give the carrier a working phone number."
                ),
            },
            {
                "q": "Why does Arizona's time offset change?",
                "a": (
                    "Most of the state keeps the same clock all year while "
                    "neighbouring states shift seasonally, so the gap moves "
                    "twice a year."
                ),
            },
            {
                "q": "Does Flagstaff need different handling?",
                "a": (
                    "In winter, yes. Let a cold sealed vial reach room "
                    "temperature before opening it, as you would anywhere with "
                    "a real winter."
                ),
            },
        ],
    },
]


REGIONS_BY_SLUG = {r["slug"]: r for r in REGIONS}


def by_market(market):
    """Every region for 'CA' or 'US', in file order.

    Kept for callers that genuinely want the whole market (the network-wide
    index). For "what does THIS storefront serve", use :func:`for_site` — market
    alone would hand the same page to five domains.
    """
    market = (market or "").upper()
    return [r for r in REGIONS if r["market"] == market]


def for_site(site):
    """The regions one storefront owns, in file order.

    This is the function views and sitemaps should use. A region belongs to
    exactly one domain, so exactly one canonical URL exists for each page.
    """
    # removeprefix, not lstrip: lstrip("www.") strips any leading w/./ character,
    # so "where-do-i-get-peptides.ca" became "here-do-i-get-peptides.ca" and
    # matched no owner at all. The site silently owned nothing.
    domain = (getattr(site, "domain", "") or "").lower()
    domain = domain.removeprefix("www.")
    return [r for r in REGIONS if r.get("owner", "").lower() == domain]


def owner_of(slug):
    """Domain that serves this region, or '' if the slug is unknown."""
    r = REGIONS_BY_SLUG.get((slug or "").strip().lower())
    return (r or {}).get("owner", "")


def cities_of(parent_slug):
    """City pages hanging off a province page (empty for most regions)."""
    return [r for r in REGIONS if r.get("parent") == parent_slug]


def get(slug):
    """One region dict by slug, or None if there is no such page.

    Returning None keeps the 404 decision in the view, where it belongs.
    """
    if not slug:
        return None
    return REGIONS_BY_SLUG.get(slug.strip().lower())


def slugs(market=None):
    """Slugs for URL generation and sitemaps, optionally filtered by market."""
    source = by_market(market) if market else REGIONS
    return [r["slug"] for r in source]
