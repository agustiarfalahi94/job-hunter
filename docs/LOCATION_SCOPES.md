# Geographic Scopes

## Selection And Evidence

Location is an empty-by-default multiselect. Any selected scope can match (OR), ignoring capitalization. Select cities, countries, or presets together, for example Kuala Lumpur OR Jakarta, or Malaysia OR Indonesia. Custom typed areas remain available after navigating away and returning. Legacy CLI `--location` remains a single-string input; `SearchCriteria.locations` provides multi-scope input internally.

Europe OR APAC is supported. Global (also typed Worldwide / Whole world) removes geographic query constraints and accepts any observed geography. It overrides other areas, does not award a universal location-score bonus, and does not increase source coverage or budgets.

Country names, common aliases, and ISO two/three-letter codes use pycountry. Short codes count only as whole address components, not prose words such as `in`. Known city-country mappings support common examples; unknown cities without country evidence are not guessed. Structured job addresses are associated with the selected vacancy, not neighboring vacancies on the same page.

Matching is three-valued: a confirmed match accepts, confirmed mismatches skip before scoring, and insufficient evidence stays unverified with a result remark. Any verified matching address is enough for a multi-location vacancy. Country-only evidence cannot prove a requested city. A selected search location is never recorded as observed posting geography.

## Presets

ASEAN: Brunei, Cambodia, Indonesia, Laos, Malaysia, Myanmar, Philippines, Singapore, Thailand, Timor-Leste, Vietnam. Timor-Leste admission: [ASEAN announcement](https://asean.org/forging-a-new-era-timor-leste-admitted-into-asean/).

APAC is an app-defined Asia-Pacific country/economy preset, not a claim about universal regional borders. It includes ASEAN plus:

- East Asia: China, Hong Kong, Macao, Taiwan, Japan, South Korea, North Korea, Mongolia.
- South Asia: India, Bangladesh, Pakistan, Sri Lanka, Nepal, Bhutan, Maldives, Afghanistan.
- Pacific: Australia, New Zealand, Fiji, Papua New Guinea, Solomon Islands, Vanuatu, Samoa, Tonga, Kiribati, Tuvalu, Nauru, Micronesia, Marshall Islands, Palau, Cook Islands, Niue, New Caledonia, French Polynesia, Guam, Northern Mariana Islands, American Samoa, Tokelau, Wallis and Futuna, Pitcairn.

The authoritative preset ISO codes live in `src/job_hunter/locations.py`. Users can select individual countries outside this preset. Country options come from [pycountry's ISO dataset](https://github.com/pycountry/pycountry), not a visitor's CV. Malaysian city suggestions retain CountriesNow API lookup and local fallback.

Europe is a geographic app preset, not EU membership: Albania, Andorra, Austria, Belarus, Belgium, Bosnia and Herzegovina, Bulgaria, Croatia, Czechia, Denmark, Estonia, Faroe Islands, Finland, France, Germany, Gibraltar, Greece, Guernsey, Holy See, Hungary, Iceland, Ireland, Isle of Man, Italy, Jersey, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Moldova, Monaco, Montenegro, Netherlands, North Macedonia, Norway, Poland, Portugal, Romania, Russia, San Marino, Serbia, Slovakia, Slovenia, Spain, Svalbard and Jan Mayen, Sweden, Switzerland, Ukraine, United Kingdom, Aland Islands. Russia is a whole-country hiring scope; Cyprus and Turkey can be added separately. This is not political/border adjudication.

## Budgets And Coverage

SerpAPI/public web discovery uses parenthesized country alternatives within existing queries. Source, title/description, and location OR groups stay independent constraints. Direct public LinkedIn fallback needs individual area queries, interleaved with other platforms, capped at twelve requests total. Broad scopes do not guarantee that every country, source, or posting is visited.

JobStreet includes regional subdomains of jobstreet.com plus jobstreet.com.my. Foundit supports its verified Malaysia, Indonesia, Singapore, and India domains. LinkedIn/Indeed have broader coverage; availability still depends on public indexing and accessible job pages.

Fifty is the maximum unique candidates collected before suitability is known, not fifty best matches or fifty per location. Stale, closed, ineligible, and location-mismatched candidates still consume checking capacity. Retained jobs are ranked only after scoring.

Company-name lookup verifies each distinct selected company-region pair and caches each result. Malaysian cities map to Malaysia; Jakarta maps to Indonesia. Other known cities map to their countries; unknown typed cities retain their literal verification scope. ASEAN/APAC remain a single broad verification scope and require grounded regional evidence. At most five company/region pairs and five resolved sites are allowed per selection; validate the pair ceiling before any provider lookup. Failed regional verification is shown, not silently dropped. Known explicit domains/presets do not consume Gemini company-name lookup pairs. Google Search grounding quota remains separate from scoring availability.
