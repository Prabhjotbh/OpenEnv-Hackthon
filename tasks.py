# All prices in Indian Rupees (INR). Conversion rate: ~83 INR/USD.
# Realistic Indian industrial market pricing (2024).

TASKS = {
    "task1_easy": {
        "id": "task1_easy",
        "description": "Single item procurement. Negotiate best price from 3 suppliers. No compliance requirements.",
        "rfq": {
            "item": "Industrial Conveyor Belt Unit",
            "quantity": 50,
            "budget": 6250000.0,        # ₹62,50,000
            "deadline_days": 30,
            "required_certs": []
        },
        "max_steps": 12,
        "suppliers": [
            {
                "id": 1, "name": "AlphaIndustries", "item_category": "mechanical",
                "quoted_price": 115000.0, "min_price": 82000.0,
                "lead_time_days": 14, "moq": 20, "reliability": 0.92,
                "quality_score": 0.88, "certifications": ["ISO9001"],
                "behavior": "flexible"
            },
            {
                "id": 2, "name": "BetaSupply", "item_category": "mechanical",
                "quoted_price": 104000.0, "min_price": 87000.0,
                "lead_time_days": 21, "moq": 50, "reliability": 0.85,
                "quality_score": 0.81, "certifications": ["ISO9001"],
                "behavior": "firm"
            },
            {
                "id": 3, "name": "GammaFab", "item_category": "mechanical",
                "quoted_price": 133000.0, "min_price": 75000.0,
                "lead_time_days": 10, "moq": 10, "reliability": 0.90,
                "quality_score": 0.86, "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            }
        ]
    },

    "task2_medium": {
        "id": "task2_medium",
        "description": "Pressure relief valve procurement. Budget-constrained. ATEX certification mandatory. One supplier has hidden quality issues.",
        "rfq": {
            "item": "Pressure Relief Valve",
            "quantity": 200,
            "budget": 25000000.0,       # ₹2,50,00,000
            "deadline_days": 21,
            "required_certs": ["ATEX"]
        },
        "max_steps": 18,
        "suppliers": [
            {
                "id": 1, "name": "SafeValveCo", "item_category": "pneumatic",
                "quoted_price": 133000.0, "min_price": 112000.0,
                "lead_time_days": 18, "moq": 100, "reliability": 0.91,
                "quality_score": 0.87, "certifications": ["ISO9001", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 2, "name": "QuickSeal Ltd", "item_category": "pneumatic",
                "quoted_price": 91000.0, "min_price": 79000.0,
                "lead_time_days": 12, "moq": 50, "reliability": 0.78,
                "quality_score": 0.48,                          # hidden quality issue
                "certifications": ["ISO9001"],                  # no ATEX
                "behavior": "flexible"
            },
            {
                "id": 3, "name": "PressurePro", "item_category": "pneumatic",
                "quoted_price": 120000.0, "min_price": 100000.0,
                "lead_time_days": 25, "moq": 200, "reliability": 0.94,
                "quality_score": 0.90, "certifications": ["ISO9001", "ATEX", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 4, "name": "ValveMart", "item_category": "pneumatic",
                "quoted_price": 112000.0, "min_price": 95000.0,
                "lead_time_days": 14, "moq": 100, "reliability": 0.82,
                "quality_score": 0.75, "certifications": ["ISO9001"],  # no ATEX
                "behavior": "firm"
            },
            {
                "id": 5, "name": "NovaSeal", "item_category": "pneumatic",
                "quoted_price": 145000.0, "min_price": 116000.0,
                "lead_time_days": 10, "moq": 50, "reliability": 0.96,
                "quality_score": 0.93, "certifications": ["ISO9001", "ATEX", "CE"],
                "behavior": "flexible"
            }
        ]
    },

    "task3_hard": {
        "id": "task3_hard",
        "description": "Hydraulic pump procurement. Tight budget. One deceptive supplier. CE + ISO9001 both required. One supplier will revise price up after soft-accept.",
        "rfq": {
            "item": "Hydraulic Pump System",
            "quantity": 30,
            "budget": 15000000.0,       # ₹1,50,00,000
            "deadline_days": 15,
            "required_certs": ["CE", "ISO9001"]
        },
        "max_steps": 25,
        "suppliers": [
            {
                "id": 1, "name": "HydroCore", "item_category": "hydraulic",
                "quoted_price": 480000.0, "min_price": 407000.0,
                "lead_time_days": 12, "moq": 10, "reliability": 0.93,
                "quality_score": 0.89, "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 2, "name": "FluidDyn", "item_category": "hydraulic",
                "quoted_price": 350000.0, "min_price": 350000.0,  # deceptive: won't honor
                "lead_time_days": 8, "moq": 5, "reliability": 0.71,
                "quality_score": 0.66, "certifications": ["ISO9001"],  # missing CE
                "behavior": "deceptive"
            },
            {
                "id": 3, "name": "PumpTech", "item_category": "hydraulic",
                "quoted_price": 515000.0, "min_price": 432000.0,
                "lead_time_days": 20, "moq": 20, "reliability": 0.88,
                "quality_score": 0.85, "certifications": ["ISO9001", "CE"],
                "behavior": "firm"
            },
            {
                "id": 4, "name": "AquaForce", "item_category": "hydraulic",
                "quoted_price": 456000.0, "min_price": 382000.0,
                "lead_time_days": 14, "moq": 10, "reliability": 0.90,
                "quality_score": 0.87, "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 5, "name": "GlobalHydro", "item_category": "hydraulic",
                "quoted_price": 580000.0, "min_price": 480000.0,
                "lead_time_days": 7, "moq": 1, "reliability": 0.97,
                "quality_score": 0.95, "certifications": ["ISO9001", "CE", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 6, "name": "EcoFlow", "item_category": "hydraulic",
                "quoted_price": 400000.0, "min_price": 374000.0,
                "lead_time_days": 18, "moq": 15, "reliability": 0.84,
                "quality_score": 0.80, "certifications": ["ISO9001"],  # missing CE
                "behavior": "flexible"
            }
        ]
    }
}
