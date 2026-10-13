// A real Gemini review of public/samples/sample-lease.pdf, with the last risk's
// quote swapped for one that isn't in the contract so the unverified state shows.

import type { ContractReview } from "./api";

export const MOCK_REVIEW: ContractReview = {
  "summary": "This residential lease agreement binds Harbor Homes LLC as the landlord and Jordan Vale as the tenant for an apartment in Port Elsby. The lease runs for one year with automatic renewal and places significant maintenance, liability, and financial obligations on the tenant.",
  "contract_type": "Residential lease",
  "parties": [
    {
      "name": "Harbor Homes LLC",
      "role": "Landlord"
    },
    {
      "name": "Jordan Vale",
      "role": "Tenant"
    }
  ],
  "key_terms": [
    {
      "label": "Lease start date",
      "value": "1 April 2026",
      "evidence": {
        "page": 1,
        "quote": "The Lease begins on 1 April 2026 and ends on 31 March 2027.",
        "verified": true
      }
    },
    {
      "label": "Lease end date",
      "value": "31 March 2027",
      "evidence": {
        "page": 1,
        "quote": "The Lease begins on 1 April 2026 and ends on 31 March 2027.",
        "verified": true
      }
    },
    {
      "label": "Monthly rent",
      "value": "1,450 USD",
      "evidence": {
        "page": 1,
        "quote": "Monthly rent is 1,450 USD, payable in advance on the first day of each month by bank transfer.",
        "verified": true
      }
    },
    {
      "label": "Late fee",
      "value": "75 USD plus 10 USD per day after the fifth of the month",
      "evidence": {
        "page": 1,
        "quote": "Rent received after the fifth day of the month incurs a late fee of 75 USD, plus 10 USD for each further",
        "verified": true
      }
    },
    {
      "label": "Security deposit",
      "value": "2,900 USD",
      "evidence": {
        "page": 1,
        "quote": "The Tenant pays a security deposit of 2,900 USD before moving in.",
        "verified": true
      }
    },
    {
      "label": "Notice period for non-renewal",
      "value": "90 days",
      "evidence": {
        "page": 1,
        "quote": "Unless either party gives written notice at least 90 days before the end of the term, this Lease renews automatically for further",
        "verified": true
      }
    },
    {
      "label": "Pet fee",
      "value": "300 USD",
      "evidence": {
        "page": 2,
        "quote": "A non-refundable pet fee of 300 USD applies.",
        "verified": true
      }
    }
  ],
  "clauses": [
    {
      "kind": "termination",
      "title": "Early termination",
      "plain_english": "After six months, the tenant can end the lease with 60 days notice and two months rent as a fee. The landlord can end the lease at any time with 30 days notice.",
      "evidence": {
        "page": 2,
        "quote": "After the first six months, the Tenant may end this Lease by giving 60 days' written notice and paying a termination fee equal to two months' rent. The Landlord may end this Lease at any",
        "verified": true
      }
    },
    {
      "kind": "renewal",
      "title": "Renewal",
      "plain_english": "The lease renews automatically for another year unless either party gives 90 days written notice before the term ends.",
      "evidence": {
        "page": 1,
        "quote": "Unless either party gives written notice at least 90 days before the end of the term, this Lease renews automatically for further",
        "verified": true
      }
    },
    {
      "kind": "payment",
      "title": "Rent and deposit",
      "plain_english": "Rent is due on the first of the month with late fees starting after the fifth. The tenant also pays a security deposit returned within 45 days minus any deductions the landlord decides.",
      "evidence": {
        "page": 1,
        "quote": "Monthly rent is 1,450 USD, payable in advance on the first day of each month by bank transfer.",
        "verified": true
      }
    },
    {
      "kind": "liability",
      "title": "Liability and insurance",
      "plain_english": "The landlord is not responsible for any damage or injury to the tenant or guests, even if caused by the landlord's negligence, and the tenant must maintain renter's insurance.",
      "evidence": {
        "page": 3,
        "quote": "The Landlord is not liable for any loss, injury or damage to the Tenant, the Tenant's guests or their property, however caused, including through the Landlord's negligence. The Tenant must hold",
        "verified": true
      }
    },
    {
      "kind": "governing_law",
      "title": "Governing law",
      "plain_english": "The lease is interpreted and enforced according to the laws of the State of Westmarch.",
      "evidence": {
        "page": 3,
        "quote": "This Lease is governed by the laws of the State of Westmarch.",
        "verified": true
      }
    },
    {
      "kind": "dispute_resolution",
      "title": "Disputes",
      "plain_english": "Any legal disputes must be handled through binding arbitration in Port Elsby, and the tenant gives up the right to a jury trial or class action.",
      "evidence": {
        "page": 3,
        "quote": "Any dispute arising out of this Lease shall be resolved by binding arbitration in Port Elsby. The Tenant waives any right to a jury trial or to join a class action.",
        "verified": true
      }
    },
    {
      "kind": "other",
      "title": "Repairs and maintenance",
      "plain_english": "The tenant must pay for all repairs to plumbing, heating, electrical, and other systems regardless of the cause, except for structural building damage.",
      "evidence": {
        "page": 2,
        "quote": "The Tenant is responsible for all repairs to the Premises, including plumbing, heating and electrical systems, whatever the cause, except damage to the structure of the",
        "verified": true
      }
    },
    {
      "kind": "other",
      "title": "Access",
      "plain_english": "The landlord and agents can enter the property at any reasonable time to inspect, repair, or show it without required prior notice.",
      "evidence": {
        "page": 2,
        "quote": "The Landlord and its agents may enter the Premises at any reasonable time to inspect, repair or show the Premises to prospective tenants or buyers. The Landlord will try to give notice but is",
        "verified": true
      }
    }
  ],
  "risks": [
    {
      "severity": "high",
      "title": "Broad repair obligations",
      "explanation": "The tenant bears the risk of paying for all repairs to plumbing, heating, and electrical systems regardless of fault, which could result in high unexpected costs.",
      "evidence": {
        "page": 2,
        "quote": "The Tenant is responsible for all repairs to the Premises, including plumbing, heating and electrical systems, whatever the cause, except damage to the structure of the",
        "verified": true
      }
    },
    {
      "severity": "high",
      "title": "Landlord waiver of liability",
      "explanation": "The tenant bears all risk for injury or property loss, even if caused by the landlord's own negligence, and must carry renter's insurance.",
      "evidence": {
        "page": 3,
        "quote": "The Landlord is not liable for any loss, injury or damage to the Tenant, the Tenant's guests or their property, however caused, including through the Landlord's negligence. The Tenant must hold",
        "verified": true
      }
    },
    {
      "severity": "medium",
      "title": "Unilateral deposit deductions",
      "explanation": "The tenant bears the risk of the landlord making subjective deductions from the security deposit based solely on the landlord's discretion.",
      "evidence": {
        "page": 1,
        "quote": "returns the deposit within 45 days after the Lease ends, less any amounts the Landlord, in its sole discretion, considers necessary for cleaning, repairs or unpaid charges.",
        "verified": true
      }
    },
    {
      "severity": "medium",
      "title": "Unilateral landlord termination",
      "explanation": "The tenant bears the risk of the landlord ending the lease at any time with only 30 days notice, offering less stability than the tenant's termination rights.",
      "evidence": {
        "page": 2,
        "quote": "notice and paying a termination fee equal to two months' rent. The Landlord may end this Lease at any time by giving 30 days' written notice.",
        "verified": true
      }
    },
    {
      "severity": "medium",
      "title": "Entry without notice",
      "explanation": "The tenant bears the risk of the landlord entering the property at any time without mandatory prior notice.",
      "evidence": {
        "page": 2,
        "quote": "repair or show the Premises to prospective tenants or buyers. The Landlord will try to give notice but is not required to do so.",
        "verified": true
      }
    },
    {
      "severity": "low",
      "title": "Waiver of jury trial and class actions",
      "explanation": "The tenant loses the right to a court trial and class action participation when resolving disputes.",
      "evidence": {
        "page": 3,
        "quote": "The Tenant gives up every right to go to court.",
        "verified": false
      }
    }
  ]
};
