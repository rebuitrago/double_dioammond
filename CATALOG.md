# Expanded Indicator Catalog — Sub-Factor Structure (FINAL)

IPS two-level hierarchy: **factor → determinant → sub-factor → criterion**. Criteria average within a sub-factor; sub-factors average within a determinant (equal weight per sub-factor), per Cho et al. (2009).

**8 determinants · 22 sub-factors · 53 criteria** (31 automatic / 22 loaded from files).

Polarity `−` = lower is better. Track A = pulled automatically by `ingest.py` (World Bank WDI/WGI, **including the WBES `IC.FRM.*` indicators**). Track B = loaded from your files via `load_datasets.py`.

## Factor Conditions
### Natural & energy endowment
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Total natural resources rents (% GDP) *(existing)* | WDI | domestic | + | A |
| PCI: Natural capital | PCI | domestic | + | B |
| PCI: Energy | PCI | domestic | + | B |

### Human capital & research
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| R&D expenditure (% GDP) *(existing)* | WDI | domestic | + | A |
| GII: Human capital & research pillar | GII | domestic | + | B |

### International factor access
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| FDI net inflows (% GDP) *(existing)* | WDI | international | + | A |
| FDI net outflows (% GDP) *(existing)* | WDI | international | + | A |
| UNCTAD: Inward FDI stock (% GDP, computed) | UNCTAD | international | + | B |
| UNCTAD: Outward FDI stock (% GDP, computed) | UNCTAD | international | + | B |

## Demand Conditions
### Demand size
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| GDP (current US$) *(existing)* | WDI | domestic | + | A |
| GDP growth (annual %) *(existing)* | WDI | domestic | + | A |

### Demand quality
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Tertiary enrollment (% gross) | WDI | domestic | + | A |

### International demand
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Exports of goods & services (% GDP) *(existing)* | WDI | international | + | A |

## Related & Supporting Industries
### Infrastructure
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Mobile subscriptions (per 100) *(existing)* | WDI | domestic | + | A |
| PCI: Transport | PCI | domestic | + | B |
| PCI: ICT | PCI | domestic | + | B |
| GII: Infrastructure pillar | GII | domestic | + | B |

### Finance
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Domestic credit to private sector (% GDP) | WDI | domestic | + | A |
| Firms with a bank loan/line of credit (% firms) | WDI | domestic | + | A |

### International connectivity
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Air transport, freight (mn ton-km) | WDI | international | + | A |
| ICT service exports (% service exports) | WDI | international | + | A |

## Firm Strategy, Structure & Rivalry
### Business environment & rivalry
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| GII: Business sophistication pillar | GII | domestic | + | B |
| PCI: Private sector | PCI | domestic | + | B |
| Bribery incidence (% firms) | WDI | domestic | - | A |
| Firms competing against unregistered firms (% firms) | WDI | domestic | - | A |

### Market openness
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Trade (% GDP) *(existing)* | WDI | international | + | A |
| Applied tariff rate, weighted mean *(existing)* | WDI | international | - | A |

## Workers
### Labor quantity
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Labor force participation rate (%) *(existing)* | WDI | domestic | + | A |

### Labor quality
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Secondary enrollment (% gross) | WDI | domestic | + | A |
| PCI: Human capital | PCI | domestic | + | B |
| Firms offering formal training (% firms) | WDI | domestic | + | A |

### International labor
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| International migrant stock (% pop) *(existing)* | WDI | international | + | A |
| Personal remittances received (% GDP) | WDI | international | + | A |

## Politicians & Bureaucrats
### Bureaucratic quality
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Government Effectiveness (estimate) *(existing)* | WGI | domestic | + | A |
| Regulatory Quality (estimate) | WGI | domestic | + | A |
| PCI: Institutions | PCI | domestic | + | B |

### Integrity & rule of law
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Control of Corruption (estimate) *(existing)* | WGI | domestic | + | A |
| Rule of Law (estimate) | WGI | domestic | + | A |
| FSI: State Legitimacy (P1) | Fund for Peace | domestic | - | B |
| FSI: Human Rights (P3) | Fund for Peace | domestic | - | B |
| FSI: Factionalized Elites (C2) | Fund for Peace | domestic | - | B |

### State capacity
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| FSI: Security Apparatus (C1) | Fund for Peace | domestic | - | B |
| FSI: Public Services (P2) | Fund for Peace | domestic | - | B |

## Entrepreneurs
### Entrepreneurial activity
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| New business density (per 1,000) *(existing)* | WDI | domestic | + | A |
| Firms introducing a new product/service (% firms) | WDI | domestic | + | A |

### Entrepreneurial environment
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| GII: Market sophistication pillar | GII | domestic | + | B |

### International entrepreneurship
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| High-technology exports (% mfg exports) *(existing)* | WDI | international | + | A |

## Professionals
### Knowledge & research talent
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| Researchers in R&D (per million) *(existing)* | WDI | domestic | + | A |
| Scientific & technical journal articles | WDI | domestic | + | A |
| GII: Knowledge & technology outputs pillar | GII | domestic | + | B |

### International professional mobility
| Criterion | Source | Context | Pol. | Track |
|---|---|---|---|---|
| International students inbound (% tertiary) *(existing)* | UNESCO | international | + | B |
| GII: knowledge diffusion (intl) | GII | international | + | B |
| FSI: Human Flight & Brain Drain (E3) | Fund for Peace | international | - | B |

## Loading your files (Track B)

Four files: **GII, PCI, FSI, UNCTAD**. WBES is now automatic (Track A) and QoG was dropped (it repackages WGI/ICRG, which we already use — avoids double counting).

| Dataset | Columns used | Country key | Notes |
|---|---|---|---|
| **GII** (WIPO) | 6 pillar/sub-pillar score columns | ISO3 | scores 0–100, headers must match exactly |
| **PCI** (UNCTAD) | 7 component columns | name → ISO3 | `year_` has a trailing underscore |
| **FSI** (Fund for Peace) | C1, C2, P1, P2, P3, E3 | name → ISO3 | scale 0–10, all polarity − |
| **UNCTAD FDI** | inward + outward **stock** | M49 → ISO3 | long format; auto-pivoted & divided by GDP |

`load_datasets.py` handles all four: GII/PCI/FSI as wide loads (name→ISO3 via the built-in resolver) and UNCTAD via a dedicated step that filters out regional aggregates, pivots stock rows, maps M49→ISO3, and divides by WDI GDP to express FDI stock as % of GDP (the paper's connectivity measure).

## Coverage notes

- **WBES `IC.FRM.*`** are sparse (survey years only, 2006–2025) and use WDI's *unweighted* aggregation rather than the ES portal's weighted figures — minor, footnote it.
- **International human factors** are now covered: FSI brain drain (E3) fills the long-empty international-Professionals corner.
- Each score carries `n_indicators`, so thin sub-factors stay visibly distinct.
