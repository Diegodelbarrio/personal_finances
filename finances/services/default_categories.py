NOT_APPLICABLE = "N/A"
INCOME = "INCOME"
EXPENSE = "EXPENSE"
FIXED = "FIXED"
VARIABLE = "VARIABLE"
NEEDS = "NEEDS"
WANTS = "WANTS"
SAVINGS = "SAVINGS"


def _subcategory(
    key,
    name,
    budget_group,
    expense_nature,
    *,
    is_essential=False,
    selected_by_default=True,
):
    return {
        "key": key,
        "name": name,
        "budget_group": budget_group,
        "expense_nature": expense_nature,
        "is_essential": is_essential,
        "selected_by_default": selected_by_default,
    }


def _category(
    key,
    name,
    transaction_type,
    expense_type,
    subcategories,
    *,
    description,
    is_housing=False,
    required=False,
    selected_by_default=True,
):
    return {
        "key": key,
        "name": name,
        "description": description,
        "transaction_type": transaction_type,
        "expense_type": expense_type,
        "is_housing": is_housing,
        "required": required,
        "selected_by_default": selected_by_default,
        "subcategories": list(subcategories),
    }


DEFAULT_CATEGORY_BLUEPRINTS = [
    _category(
        "income",
        "Income",
        INCOME,
        NOT_APPLICABLE,
        [
            _subcategory("income_salary", "Salary", NOT_APPLICABLE, NOT_APPLICABLE),
            _subcategory("income_freelance", "Freelance", NOT_APPLICABLE, NOT_APPLICABLE),
            _subcategory("income_bonus", "Bonus", NOT_APPLICABLE, NOT_APPLICABLE),
            _subcategory("income_dividends", "Interest & Dividends", NOT_APPLICABLE, NOT_APPLICABLE),
            _subcategory("income_other", "Other Income", NOT_APPLICABLE, NOT_APPLICABLE),
        ],
        description="Money coming in from work, returns, and other sources.",
        required=True,
    ),
    _category(
        "housing",
        "Housing",
        EXPENSE,
        FIXED,
        [
            _subcategory("housing_rent", "Rent or Mortgage", NEEDS, FIXED, is_essential=True),
            _subcategory("housing_community", "HOA / Community Fees", NEEDS, FIXED),
            _subcategory("housing_insurance", "Home or Renters Insurance", NEEDS, FIXED),
            _subcategory("housing_maintenance", "Maintenance & Repairs", NEEDS, VARIABLE),
            _subcategory("housing_supplies", "Home Supplies", NEEDS, VARIABLE),
        ],
        description="The cost of keeping a safe place to live.",
        is_housing=True,
    ),
    _category(
        "utilities",
        "Utilities & Bills",
        EXPENSE,
        FIXED,
        [
            _subcategory("utilities_electricity", "Electricity", NEEDS, VARIABLE, is_essential=True),
            _subcategory("utilities_water", "Water", NEEDS, VARIABLE, is_essential=True),
            _subcategory("utilities_gas", "Gas / Heating", NEEDS, VARIABLE, is_essential=True),
            _subcategory("utilities_internet", "Internet", NEEDS, FIXED, is_essential=True),
            _subcategory("utilities_mobile", "Mobile Phone", NEEDS, FIXED),
            _subcategory("utilities_software", "Cloud & Software", WANTS, FIXED, selected_by_default=False),
        ],
        description="Recurring household services and communication bills.",
    ),
    _category(
        "food",
        "Food",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("food_grocery", "Groceries", NEEDS, VARIABLE, is_essential=True),
            _subcategory("food_market", "Market / Fresh Food", NEEDS, VARIABLE, is_essential=True),
            _subcategory("food_restaurants", "Restaurants", WANTS, VARIABLE),
            _subcategory("food_delivery", "Delivery / Takeout", WANTS, VARIABLE),
            _subcategory("food_snacks", "Coffee & Snacks", WANTS, VARIABLE),
            _subcategory("food_treats", "Alcohol & Treats", WANTS, VARIABLE, selected_by_default=False),
        ],
        description="Separate essential groceries from lifestyle food spending.",
    ),
    _category(
        "transport",
        "Transportation",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("transport_public", "Public Transport", NEEDS, VARIABLE, is_essential=True),
            _subcategory("transport_fuel", "Fuel", NEEDS, VARIABLE),
            _subcategory("transport_rideshare", "Taxi / Ride Share", WANTS, VARIABLE),
            _subcategory("transport_maintenance", "Vehicle Maintenance", NEEDS, VARIABLE),
            _subcategory("transport_tolls", "Parking & Tolls", WANTS, VARIABLE),
            _subcategory("transport_registration", "Registration & Inspection", NEEDS, FIXED),
        ],
        description="Commuting, car costs, and occasional mobility.",
    ),
    _category(
        "health",
        "Health",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("health_insurance", "Health Insurance", NEEDS, FIXED),
            _subcategory("health_pharmacy", "Pharmacy", NEEDS, VARIABLE),
            _subcategory("health_visits", "Medical Visits & Tests", NEEDS, VARIABLE),
            _subcategory("health_dental", "Dental & Vision", NEEDS, VARIABLE),
            _subcategory("health_wellness", "Wellness & Fitness", WANTS, VARIABLE),
        ],
        description="Medical essentials and wellness choices.",
    ),
    _category(
        "insurance",
        "Insurance",
        EXPENSE,
        FIXED,
        [
            _subcategory("insurance_car", "Car Insurance", NEEDS, FIXED),
            _subcategory("insurance_life", "Life Insurance", NEEDS, FIXED, selected_by_default=False),
            _subcategory("insurance_disability", "Disability Insurance", NEEDS, FIXED, selected_by_default=False),
            _subcategory("insurance_pet", "Pet Insurance", WANTS, FIXED, selected_by_default=False),
            _subcategory("insurance_other", "Other Insurance", NEEDS, FIXED),
        ],
        description="Protection payments that are not directly tied to one purchase.",
    ),
    _category(
        "debt",
        "Debt Payments",
        EXPENSE,
        FIXED,
        [
            _subcategory("debt_credit_card", "Credit Card Payment", SAVINGS, FIXED),
            _subcategory("debt_personal_loan", "Personal Loan", SAVINGS, FIXED),
            _subcategory("debt_student_loan", "Student Loan", SAVINGS, FIXED, selected_by_default=False),
            _subcategory("debt_car_loan", "Car Loan", SAVINGS, FIXED, selected_by_default=False),
            _subcategory("debt_extra_payment", "Extra Debt Payment", SAVINGS, VARIABLE),
        ],
        description="Principal debt payments tracked in the 20% bucket.",
    ),
    _category(
        "savings",
        "Savings & Investments",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("savings_emergency", "Emergency Fund", SAVINGS, VARIABLE, is_essential=True),
            _subcategory("savings_index", "Index Investing", SAVINGS, VARIABLE),
            _subcategory("savings_retirement", "Retirement Plan", SAVINGS, VARIABLE),
            _subcategory("savings_goals", "Goal-Based Savings", SAVINGS, VARIABLE),
            _subcategory("savings_cash_buffer", "Cash Buffer", SAVINGS, VARIABLE),
        ],
        description="Money intentionally moved toward savings and investing.",
    ),
    _category(
        "personal_care",
        "Personal Care",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("personal_hygiene", "Toiletries & Hygiene", NEEDS, VARIABLE),
            _subcategory("personal_haircuts", "Haircuts & Grooming", WANTS, VARIABLE),
            _subcategory("personal_beauty", "Beauty & Cosmetics", WANTS, VARIABLE),
            _subcategory("personal_laundry", "Laundry & Dry Cleaning", NEEDS, VARIABLE),
        ],
        description="Care items that do not fit neatly into health or shopping.",
    ),
    _category(
        "shopping",
        "Shopping",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("shopping_clothing_basics", "Clothing Basics", NEEDS, VARIABLE),
            _subcategory("shopping_apparel", "Apparel & Accessories", WANTS, VARIABLE),
            _subcategory("shopping_electronics", "Electronics", WANTS, VARIABLE),
            _subcategory("shopping_home_decor", "Home Decor", WANTS, VARIABLE),
            _subcategory("shopping_online", "Online Shopping", WANTS, VARIABLE),
        ],
        description="Personal purchases split between essentials and wants.",
    ),
    _category(
        "leisure",
        "Entertainment & Lifestyle",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("leisure_streaming", "Streaming", WANTS, FIXED),
            _subcategory("leisure_events", "Events", WANTS, VARIABLE),
            _subcategory("leisure_hobbies", "Hobbies", WANTS, VARIABLE),
            _subcategory("leisure_games", "Games & Apps", WANTS, VARIABLE),
            _subcategory("leisure_social", "Social Plans", WANTS, VARIABLE),
        ],
        description="Non-essential spending that makes life more enjoyable.",
    ),
    _category(
        "travel",
        "Travel",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("travel_general", "Travel", WANTS, VARIABLE),
            _subcategory("travel_transport", "Flights & Transport", WANTS, VARIABLE),
            _subcategory("travel_lodging", "Hotels & Lodging", WANTS, VARIABLE),
            _subcategory("travel_food", "Travel Food", WANTS, VARIABLE),
            _subcategory("travel_activities", "Tours & Activities", WANTS, VARIABLE),
            _subcategory("travel_insurance", "Travel Insurance", WANTS, VARIABLE),
        ],
        description="Trip costs that benefit from location-based tracking.",
        selected_by_default=False,
    ),
    _category(
        "education",
        "Education & Professional",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("education_books", "Books", WANTS, VARIABLE),
            _subcategory("education_courses", "Courses", WANTS, VARIABLE),
            _subcategory("education_tools", "Learning Tools", WANTS, FIXED),
            _subcategory("education_certifications", "Certifications", WANTS, VARIABLE),
            _subcategory("education_work_expenses", "Work Expenses", NEEDS, VARIABLE, selected_by_default=False),
        ],
        description="Learning, career growth, and professional costs.",
        selected_by_default=False,
    ),
    _category(
        "family_pets",
        "Family & Pets",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("family_childcare", "Childcare", NEEDS, FIXED),
            _subcategory("family_school", "School & Kids", NEEDS, VARIABLE),
            _subcategory("family_pet_food", "Pet Food & Care", NEEDS, VARIABLE),
            _subcategory("family_pet_vet", "Vet", NEEDS, VARIABLE),
            _subcategory("family_activities", "Family Activities", WANTS, VARIABLE),
        ],
        description="Dependents, kids, and pet-related spending.",
        selected_by_default=False,
    ),
    _category(
        "gifts_donations",
        "Gifts & Donations",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("gifts_birthdays", "Birthdays & Holidays", WANTS, VARIABLE),
            _subcategory("gifts_charity", "Charity & Donations", WANTS, VARIABLE),
            _subcategory("gifts_weddings", "Weddings & Events", WANTS, VARIABLE),
        ],
        description="Irregular generosity and celebration costs.",
        selected_by_default=False,
    ),
    _category(
        "taxes_fees",
        "Taxes & Fees",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("taxes_income", "Income Tax", NEEDS, VARIABLE),
            _subcategory("taxes_bank_fees", "Bank Fees", NEEDS, VARIABLE),
            _subcategory("taxes_admin", "Legal & Admin", NEEDS, VARIABLE),
            _subcategory("taxes_fines", "Fines & Penalties", WANTS, VARIABLE, selected_by_default=False),
        ],
        description="Administrative costs that are easy to miss in budgets.",
    ),
    _category(
        "misc",
        "Miscellaneous",
        EXPENSE,
        VARIABLE,
        [
            _subcategory("misc_unplanned", "Unplanned Essentials", NEEDS, VARIABLE),
            _subcategory("misc_cash", "Cash / ATM", WANTS, VARIABLE),
            _subcategory("misc_adjustments", "Adjustments", WANTS, VARIABLE),
            _subcategory("misc_other", "Other Expense", WANTS, VARIABLE),
        ],
        description="A small safety net for expenses that do not have a home yet.",
    ),
]


def get_default_category_blueprints():
    return DEFAULT_CATEGORY_BLUEPRINTS
