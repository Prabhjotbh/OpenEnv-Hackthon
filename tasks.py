# All prices in Indian Rupees (INR). Conversion rate: ~92 INR/USD.
# Supplier names are real Indian industrial market participants in each product category.
# Pricing reflects 2024-25 Indian market rates for OEM/B2B procurement.

TASKS = {
    "task1_easy": {
        "id": "task1_easy",
        "description": (
            "Conveyor belt unit procurement for a warehouse expansion project. "
            "Three suppliers, all willing to negotiate. No compliance requirements -- "
            "focus is entirely on getting the best price within budget."
        ),
        "rfq": {
            "item": "Industrial Conveyor Belt Unit",
            "quantity": 50,
            "budget": 6900000.0,        # ₹69,00,000 (~$75,000 at 92)
            "deadline_days": 30,
            "required_certs": []
        },
        "max_steps": 12,
        "suppliers": [
            {
                "id": 1,
                "name": "Fenner India Ltd",
                "location": "Pune",
                "item_category": "mechanical",
                "quoted_price": 128000.0,   # ₹1,28,000/unit
                "min_price": 91000.0,        # ₹91,000/unit
                "lead_time_days": 14,
                "moq": 20,
                "reliability": 0.92,
                "quality_score": 0.88,
                "certifications": ["ISO9001"],
                "behavior": "flexible"
            },
            {
                "id": 2,
                "name": "Bando Power Transmission",
                "location": "Chennai",
                "item_category": "mechanical",
                "quoted_price": 115000.0,   # ₹1,15,000/unit
                "min_price": 97000.0,        # ₹97,000/unit
                "lead_time_days": 21,
                "moq": 50,
                "reliability": 0.85,
                "quality_score": 0.81,
                "certifications": ["ISO9001"],
                "behavior": "firm"
            },
            {
                "id": 3,
                "name": "Dunlop Conveyor Belting",
                "location": "Kolkata",
                "item_category": "mechanical",
                "quoted_price": 147000.0,   # ₹1,47,000/unit
                "min_price": 83000.0,        # ₹83,000/unit -- best floor, but higher quote
                "lead_time_days": 10,
                "moq": 10,
                "reliability": 0.90,
                "quality_score": 0.86,
                "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            }
        ]
    },

    "task2_medium": {
        "id": "task2_medium",
        "description": (
            "Pressure relief valve procurement for a refinery process line. "
            "ATEX certification is mandatory -- the installation is in a Zone 1 "
            "hazardous area. One supplier (QuickSeal) has a low quality score and "
            "no ATEX cert but quotes aggressively. Accepting them fails compliance."
        ),
        "rfq": {
            "item": "Pressure Relief Valve",
            "quantity": 200,
            "budget": 27600000.0,       # ₹2,76,00,000 (~$300,000 at 92)
            "deadline_days": 21,
            "required_certs": ["ATEX"]
        },
        "max_steps": 18,
        "suppliers": [
            {
                "id": 1,
                "name": "Forbes Marshall",
                "location": "Pune",
                "item_category": "pneumatic",
                "quoted_price": 147000.0,   # over budget at quoted, must negotiate
                "min_price": 124000.0,
                "lead_time_days": 18,
                "moq": 100,
                "reliability": 0.91,
                "quality_score": 0.87,
                "certifications": ["ISO9001", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 2,
                "name": "QuickSeal Valves Pvt",
                "location": "Surat",
                "item_category": "pneumatic",
                "quoted_price": 101000.0,
                "min_price": 88000.0,
                "lead_time_days": 12,
                "moq": 50,
                "reliability": 0.78,
                "quality_score": 0.48,          # below threshold -- do not accept
                "certifications": ["ISO9001"],   # no ATEX
                "behavior": "flexible"
            },
            {
                "id": 3,
                "name": "Spirax Sarco India",
                "location": "Mumbai",
                "item_category": "pneumatic",
                "quoted_price": 133000.0,
                "min_price": 111000.0,
                "lead_time_days": 25,
                "moq": 200,
                "reliability": 0.94,
                "quality_score": 0.90,
                "certifications": ["ISO9001", "ATEX", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 4,
                "name": "L&T Valves",
                "location": "Chennai",
                "item_category": "pneumatic",
                "quoted_price": 124000.0,
                "min_price": 105000.0,
                "lead_time_days": 14,
                "moq": 100,
                "reliability": 0.82,
                "quality_score": 0.75,
                "certifications": ["ISO9001"],   # no ATEX
                "behavior": "firm"
            },
            {
                "id": 5,
                "name": "Audco India",
                "location": "Chennai",
                "item_category": "pneumatic",
                "quoted_price": 161000.0,
                "min_price": 129000.0,
                "lead_time_days": 10,
                "moq": 50,
                "reliability": 0.96,
                "quality_score": 0.93,
                "certifications": ["ISO9001", "ATEX", "CE"],
                "behavior": "flexible"
            }
        ]
    },

    "task3_hard": {
        "id": "task3_hard",
        "description": (
            "Hydraulic pump system procurement for a manufacturing plant retrofit. "
            "CE + ISO9001 both mandatory. Budget is tight -- only four suppliers can "
            "come in under budget even at min price. FluidDyn Systems quotes lowest "
            "and will accept any offer during negotiation, then revises up 20% on "
            "the formal accept() call. Two other suppliers are missing CE certification."
        ),
        "rfq": {
            "item": "Hydraulic Pump System",
            "quantity": 30,
            "budget": 16560000.0,       # ₹1,65,60,000 (~$180,000 at 92)
            "deadline_days": 15,
            "required_certs": ["CE", "ISO9001"]
        },
        "max_steps": 25,
        "suppliers": [
            {
                "id": 1,
                "name": "Wipro Infrastructure Engineering",
                "location": "Bangalore",
                "item_category": "hydraulic",
                "quoted_price": 532000.0,   # ₹5,32,000/unit; 30 units = ₹1,59,60,000 (in budget)
                "min_price": 451000.0,
                "lead_time_days": 12,
                "moq": 10,
                "reliability": 0.93,
                "quality_score": 0.89,
                "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 2,
                "name": "FluidDyn Systems",
                "location": "Hyderabad",
                "item_category": "hydraulic",
                "quoted_price": 388000.0,   # lowest quote -- trap
                "min_price": 388000.0,      # deceptive: floor = quote, springs +20% on accept
                "lead_time_days": 8,
                "moq": 5,
                "reliability": 0.71,
                "quality_score": 0.66,
                "certifications": ["ISO9001"],   # missing CE
                "behavior": "deceptive"
            },
            {
                "id": 3,
                "name": "Bosch Rexroth India",
                "location": "Ahmedabad",
                "item_category": "hydraulic",
                "quoted_price": 571000.0,   # over budget at quoted -- needs negotiation
                "min_price": 479000.0,
                "lead_time_days": 20,
                "moq": 20,
                "reliability": 0.88,
                "quality_score": 0.85,
                "certifications": ["ISO9001", "CE"],
                "behavior": "firm"
            },
            {
                "id": 4,
                "name": "Parker Hannifin India",
                "location": "Pune",
                "item_category": "hydraulic",
                "quoted_price": 505000.0,   # ₹5,05,000/unit; 30 units = ₹1,51,50,000 (in budget)
                "min_price": 423000.0,
                "lead_time_days": 14,
                "moq": 10,
                "reliability": 0.90,
                "quality_score": 0.87,
                "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 5,
                "name": "Yuken India",
                "location": "Bangalore",
                "item_category": "hydraulic",
                "quoted_price": 643000.0,   # over budget at quoted -- needs significant negotiation
                "min_price": 532000.0,       # 30 units = ₹1,59,60,000 (in budget at floor)
                "lead_time_days": 7,
                "moq": 1,
                "reliability": 0.97,
                "quality_score": 0.95,
                "certifications": ["ISO9001", "CE", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 6,
                "name": "Eaton Hydraulics India",
                "location": "Delhi",
                "item_category": "hydraulic",
                "quoted_price": 443000.0,
                "min_price": 415000.0,
                "lead_time_days": 18,
                "moq": 15,
                "reliability": 0.84,
                "quality_score": 0.80,
                "certifications": ["ISO9001"],   # missing CE -- disqualified
                "behavior": "flexible"
            }
        ]
    }
}
