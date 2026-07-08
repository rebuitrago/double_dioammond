-- migration 02: FINAL expanded sub-factor catalog (run AFTER migration_01). Idempotent.

insert into sub_factor (determinant_id, name, position)
select d.id, v.sf, v.pos from determinant d join (values
  ('Factor Conditions','Natural & energy endowment',1),
  ('Factor Conditions','Human capital & research',2),
  ('Factor Conditions','International factor access',3),
  ('Demand Conditions','Demand size',1),
  ('Demand Conditions','Demand quality',2),
  ('Demand Conditions','International demand',3),
  ('Related & Supporting Industries','Infrastructure',1),
  ('Related & Supporting Industries','Finance',2),
  ('Related & Supporting Industries','International connectivity',3),
  ('Firm Strategy, Structure & Rivalry','Business environment & rivalry',1),
  ('Firm Strategy, Structure & Rivalry','Market openness',2),
  ('Workers','Labor quantity',1),
  ('Workers','Labor quality',2),
  ('Workers','International labor',3),
  ('Politicians & Bureaucrats','Bureaucratic quality',1),
  ('Politicians & Bureaucrats','Integrity & rule of law',2),
  ('Politicians & Bureaucrats','State capacity',3),
  ('Entrepreneurs','Entrepreneurial activity',1),
  ('Entrepreneurs','Entrepreneurial environment',2),
  ('Entrepreneurs','International entrepreneurship',3),
  ('Professionals','Knowledge & research talent',1),
  ('Professionals','International professional mobility',2)
) as v(det, sf, pos) on v.det = d.name on conflict (determinant_id, name) do nothing;

insert into indicator (determinant_id, sub_factor_id, context, name, source, source_code, polarity, method, coverage, track)
select d.id, sf.id, v.context::context_kind, v.name, v.source, v.code,
       v.polarity::polarity_kind, v.method::norm_method, v.coverage::coverage_flag, v.track::track_kind
from sub_factor sf join determinant d on d.id = sf.determinant_id join (values
  ('Factor Conditions','Natural & energy endowment','domestic','PCI: Natural capital','PCI','PCI.NATURAL_CAPITAL','+','ratio_max','good','B'),
  ('Factor Conditions','Natural & energy endowment','domestic','PCI: Energy','PCI','PCI.ENERGY','+','ratio_max','good','B'),
  ('Factor Conditions','Human capital & research','domestic','GII: Human capital & research pillar','GII','GII.HUMAN_CAPITAL_RESEARCH','+','ratio_max','good','B'),
  ('Factor Conditions','International factor access','international','UNCTAD: Inward FDI stock (% GDP, computed)','UNCTAD','UNCTAD.FDI.STOCK.IN','+','ratio_max','good','B'),
  ('Factor Conditions','International factor access','international','UNCTAD: Outward FDI stock (% GDP, computed)','UNCTAD','UNCTAD.FDI.STOCK.OUT','+','ratio_max','good','B'),
  ('Demand Conditions','Demand quality','domestic','Tertiary enrollment (% gross)','WDI','SE.TER.ENRR','+','ratio_max','good','A'),
  ('Related & Supporting Industries','Infrastructure','domestic','PCI: Transport','PCI','PCI.TRANSPORT','+','ratio_max','good','B'),
  ('Related & Supporting Industries','Infrastructure','domestic','PCI: ICT','PCI','PCI.ICT','+','ratio_max','good','B'),
  ('Related & Supporting Industries','Infrastructure','domestic','GII: Infrastructure pillar','GII','GII.INFRASTRUCTURE','+','ratio_max','good','B'),
  ('Related & Supporting Industries','Finance','domestic','Domestic credit to private sector (% GDP)','WDI','FS.AST.PRVT.GD.ZS','+','ratio_max','good','A'),
  ('Related & Supporting Industries','Finance','domestic','Firms with a bank loan/line of credit (% firms)','WDI','IC.FRM.BNKL.ZS','+','ratio_max','patchy','A'),
  ('Related & Supporting Industries','International connectivity','international','Air transport, freight (mn ton-km)','WDI','IS.AIR.GOOD.MT.K1','+','ratio_max','good','A'),
  ('Related & Supporting Industries','International connectivity','international','ICT service exports (% service exports)','WDI','BX.GSR.CCIS.ZS','+','ratio_max','patchy','A'),
  ('Firm Strategy, Structure & Rivalry','Business environment & rivalry','domestic','GII: Business sophistication pillar','GII','GII.BUSINESS_SOPHISTICATION','+','ratio_max','good','B'),
  ('Firm Strategy, Structure & Rivalry','Business environment & rivalry','domestic','PCI: Private sector','PCI','PCI.PRIVATE_SECTOR','+','ratio_max','good','B'),
  ('Firm Strategy, Structure & Rivalry','Business environment & rivalry','domestic','Bribery incidence (% firms)','WDI','IC.FRM.BRIB.ZS','-','ratio_max','patchy','A'),
  ('Firm Strategy, Structure & Rivalry','Business environment & rivalry','domestic','Firms competing against unregistered firms (% firms)','WDI','IC.FRM.CMPU.ZS','-','ratio_max','patchy','A'),
  ('Workers','Labor quality','domestic','Secondary enrollment (% gross)','WDI','SE.SEC.ENRR','+','ratio_max','good','A'),
  ('Workers','Labor quality','domestic','PCI: Human capital','PCI','PCI.HUMAN_CAPITAL','+','ratio_max','good','B'),
  ('Workers','Labor quality','domestic','Firms offering formal training (% firms)','WDI','IC.FRM.TRNG.ZS','+','ratio_max','patchy','A'),
  ('Workers','International labor','international','Personal remittances received (% GDP)','WDI','BX.TRF.PWKR.DT.GD.ZS','+','ratio_max','good','A'),
  ('Politicians & Bureaucrats','Bureaucratic quality','domestic','Regulatory Quality (estimate)','WGI','RQ.EST','+','minmax','good','A'),
  ('Politicians & Bureaucrats','Bureaucratic quality','domestic','PCI: Institutions','PCI','PCI.INSTITUTIONS','+','ratio_max','good','B'),
  ('Politicians & Bureaucrats','Integrity & rule of law','domestic','Rule of Law (estimate)','WGI','RL.EST','+','minmax','good','A'),
  ('Politicians & Bureaucrats','Integrity & rule of law','domestic','FSI: State Legitimacy (P1)','Fund for Peace','FSI.P1_LEGITIMACY','-','ratio_max','good','B'),
  ('Politicians & Bureaucrats','Integrity & rule of law','domestic','FSI: Human Rights (P3)','Fund for Peace','FSI.P3_HUMAN_RIGHTS','-','ratio_max','good','B'),
  ('Politicians & Bureaucrats','Integrity & rule of law','domestic','FSI: Factionalized Elites (C2)','Fund for Peace','FSI.C2_ELITES','-','ratio_max','good','B'),
  ('Politicians & Bureaucrats','State capacity','domestic','FSI: Security Apparatus (C1)','Fund for Peace','FSI.C1_SECURITY','-','ratio_max','good','B'),
  ('Politicians & Bureaucrats','State capacity','domestic','FSI: Public Services (P2)','Fund for Peace','FSI.P2_PUBLIC_SVC','-','ratio_max','good','B'),
  ('Entrepreneurs','Entrepreneurial activity','domestic','Firms introducing a new product/service (% firms)','WDI','IC.FRM.NPRD.ZS','+','ratio_max','patchy','A'),
  ('Entrepreneurs','Entrepreneurial environment','domestic','GII: Market sophistication pillar','GII','GII.MARKET_SOPHISTICATION','+','ratio_max','good','B'),
  ('Professionals','Knowledge & research talent','domestic','Scientific & technical journal articles','WDI','IP.JRN.ARTC.SC','+','ratio_max','good','A'),
  ('Professionals','Knowledge & research talent','domestic','GII: Knowledge & technology outputs pillar','GII','GII.KNOWLEDGE_TECH_OUTPUTS','+','ratio_max','good','B'),
  ('Professionals','International professional mobility','international','GII: knowledge diffusion (intl)','GII','GII.KNOWLEDGE_DIFFUSION','+','ratio_max','patchy','B'),
  ('Professionals','International professional mobility','international','FSI: Human Flight & Brain Drain (E3)','Fund for Peace','FSI.E3_BRAIN_DRAIN','-','ratio_max','good','B')
) as v(det, sf, context, name, source, code, polarity, method, coverage, track)
  on v.det = d.name and v.sf = sf.name on conflict (determinant_id, context, name) do nothing;

-- reassign existing criteria into sub-factors
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Factor Conditions' and sf.name='Natural & energy endowment') where source_code = 'NY.GDP.TOTL.RT.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Factor Conditions' and sf.name='Human capital & research') where source_code = 'GB.XPD.RSDV.GD.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Factor Conditions' and sf.name='International factor access') where source_code = 'BX.KLT.DINV.WD.GD.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Factor Conditions' and sf.name='International factor access') where source_code = 'BM.KLT.DINV.WD.GD.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Demand Conditions' and sf.name='Demand size') where source_code = 'NY.GDP.MKTP.CD';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Demand Conditions' and sf.name='Demand size') where source_code = 'NY.GDP.MKTP.KD.ZG';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Demand Conditions' and sf.name='International demand') where source_code = 'NE.EXP.GNFS.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Related & Supporting Industries' and sf.name='Infrastructure') where source_code = 'IT.CEL.SETS.P2';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Firm Strategy, Structure & Rivalry' and sf.name='Market openness') where source_code = 'NE.TRD.GNFS.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Firm Strategy, Structure & Rivalry' and sf.name='Market openness') where source_code = 'TM.TAX.MRCH.WM.AR.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Workers' and sf.name='Labor quantity') where source_code = 'SL.TLF.CACT.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Workers' and sf.name='International labor') where source_code = 'SM.POP.TOTL.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Politicians & Bureaucrats' and sf.name='Bureaucratic quality') where source_code = 'GE.EST';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Politicians & Bureaucrats' and sf.name='Integrity & rule of law') where source_code = 'CC.EST';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Entrepreneurs' and sf.name='Entrepreneurial activity') where source_code = 'IC.BUS.NDNS.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Entrepreneurs' and sf.name='International entrepreneurship') where source_code = 'TX.VAL.TECH.MF.ZS';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Professionals' and sf.name='Knowledge & research talent') where source_code = 'SP.POP.SCIE.RD.P6';
update indicator set sub_factor_id = (select sf.id from sub_factor sf join determinant d on d.id=sf.determinant_id where d.name='Professionals' and sf.name='International professional mobility') where name = 'International students inbound (% tertiary)';
