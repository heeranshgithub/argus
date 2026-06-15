/**
 * Report wire types — mirror the backend's `ReportOut` (see backend
 * `app/models/report.py`). The nine required sections, camelCase.
 */

export interface BusinessSignal {
  category: string;
  summary: string;
  evidenceUrls: string[];
  confidence: number; // 0..1
}

export interface DiscoveryQuestion {
  question: string;
  rationale: string;
}

export interface ReportSource {
  url: string;
  title: string;
  /** Section anchors that cited this source. */
  usedIn: string[];
}

export interface Report {
  id: string;
  sessionId: string;
  companyOverview: string;
  productsAndServices: string[];
  targetCustomers: string[];
  businessSignals: BusinessSignal[];
  risksAndChallenges: string[];
  suggestedDiscoveryQuestions: DiscoveryQuestion[];
  suggestedOutreachStrategy: string;
  unknowns: string[];
  sources: ReportSource[];
  createdAt: string; // ISO 8601
}
