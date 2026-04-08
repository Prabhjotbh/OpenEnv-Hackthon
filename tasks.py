TASKS = {
    "task1_easy": {
        "id": "task1_easy",
        "description": "Single item procurement. Negotiate best price from 3 suppliers. No compliance requirements.",
        "rfq": {
            "item": "Industrial Conveyor Belt Unit",
            "quantity": 50,
            "budget": 75000.0,
            "deadline_days": 30,
            "required_certs": []
        },
        "max_steps": 12,
        "suppliers": [
            {
                "id": 1, "name": "AlphaIndustries", "item_category": "mechanical",
                "quoted_price": 1400.0, "min_price": 980.0,
                "lead_time_days": 14, "moq": 20, "reliability": 0.92,
                "quality_score": 0.88, "certifications": ["ISO9001"],
                "behavior": "flexible"
            },
            {
                "id": 2, "name": "BetaSupply", "item_category": "mechanical",
                "quoted_price": 1250.0, "min_price": 1050.0,
                "lead_time_days": 21, "moq": 50, "reliability": 0.85,
                "quality_score": 0.81, "certifications": ["ISO9001"],
                "behavior": "firm"
            },
            {
                "id": 3, "name": "GammaFab", "item_category": "mechanical",
                "quoted_price": 1600.0, "min_price": 900.0,
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
            "budget": 300000.0,
            "deadline_days": 21,
            "required_certs": ["ATEX"]
        },
        "max_steps": 18,
        "suppliers": [
            {
                "id": 1, "name": "SafeValveCo", "item_category": "pneumatic",
                "quoted_price": 1600.0, "min_price": 1350.0,
                "lead_time_days": 18, "moq": 100, "reliability": 0.91,
                "quality_score": 0.87, "certifications": ["ISO9001", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 2, "name": "QuickSeal Ltd", "item_category": "pneumatic",
                "quoted_price": 1100.0, "min_price": 950.0,
                "lead_time_days": 12, "moq": 50, "reliability": 0.78,
                "quality_score": 0.48,
                "certifications": ["ISO9001"],
                "behavior": "flexible"
            },
            {
                "id": 3, "name": "PressurePro", "item_category": "pneumatic",
                "quoted_price": 1450.0, "min_price": 1200.0,
                "lead_time_days": 25, "moq": 200, "reliability": 0.94,
                "quality_score": 0.90, "certifications": ["ISO9001", "ATEX", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 4, "name": "ValveMart", "item_category": "pneumatic",
                "quoted_price": 1350.0, "min_price": 1150.0,
                "lead_time_days": 14, "moq": 100, "reliability": 0.82,
                "quality_score": 0.75, "certifications": ["ISO9001"],
                "behavior": "firm"
            },
            {
                "id": 5, "name": "NovaSeal", "item_category": "pneumatic",
                "quoted_price": 1750.0, "min_price": 1400.0,
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
            "budget": 180000.0,
            "deadline_days": 15,
            "required_certs": ["CE", "ISO9001"]
        },
        "max_steps": 25,
        "suppliers": [
            {
                "id": 1, "name": "HydroCore", "item_category": "hydraulic",
                "quoted_price": 5800.0, "min_price": 4900.0,
                "lead_time_days": 12, "moq": 10, "reliability": 0.93,
                "quality_score": 0.89, "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 2, "name": "FluidDyn", "item_category": "hydraulic",
                "quoted_price": 4200.0, "min_price": 4200.0,
                "lead_time_days": 8, "moq": 5, "reliability": 0.71,
                "quality_score": 0.66, "certifications": ["ISO9001"],
                "behavior": "deceptive"
            },
            {
                "id": 3, "name": "PumpTech", "item_category": "hydraulic",
                "quoted_price": 6200.0, "min_price": 5200.0,
                "lead_time_days": 20, "moq": 20, "reliability": 0.88,
                "quality_score": 0.85, "certifications": ["ISO9001", "CE"],
                "behavior": "firm"
            },
            {
                "id": 4, "name": "AquaForce", "item_category": "hydraulic",
                "quoted_price": 5500.0, "min_price": 4600.0,
                "lead_time_days": 14, "moq": 10, "reliability": 0.90,
                "quality_score": 0.87, "certifications": ["ISO9001", "CE"],
                "behavior": "flexible"
            },
            {
                "id": 5, "name": "GlobalHydro", "item_category": "hydraulic",
                "quoted_price": 7000.0, "min_price": 5800.0,
                "lead_time_days": 7, "moq": 1, "reliability": 0.97,
                "quality_score": 0.95, "certifications": ["ISO9001", "CE", "ATEX"],
                "behavior": "firm"
            },
            {
                "id": 6, "name": "EcoFlow", "item_category": "hydraulic",
                "quoted_price": 4800.0, "min_price": 4500.0,
                "lead_time_days": 18, "moq": 15, "reliability": 0.84,
                "quality_score": 0.80, "certifications": ["ISO9001"],
                "behavior": "flexible"
            }
        ]
    }
}
