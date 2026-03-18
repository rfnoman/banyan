from .driver import get_driver

CONSTRAINTS = [
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE",
    "CREATE CONSTRAINT business_id IF NOT EXISTS FOR (b:Business) REQUIRE b.id IS UNIQUE",
    "CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT lead_id IF NOT EXISTS FOR (l:Lead) REQUIRE l.id IS UNIQUE",
    "CREATE CONSTRAINT action_id IF NOT EXISTS FOR (a:Action) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT source_name_unique IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE",
]

INDEXES = [
    "CREATE INDEX person_email_idx IF NOT EXISTS FOR (p:Person) ON (p.email)",
    "CREATE INDEX person_score_idx IF NOT EXISTS FOR (p:Person) ON (p.score)",
    "CREATE INDEX person_ai_tag_status_idx IF NOT EXISTS FOR (p:Person) ON (p.ai_tag_status)",
    "CREATE INDEX lead_stage_idx IF NOT EXISTS FOR (l:Lead) ON (l.stage)",
    "CREATE INDEX product_name_idx IF NOT EXISTS FOR (p:Product) ON (p.name)",
]


def apply_schema():
    driver = get_driver()
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
        for stmt in INDEXES:
            session.run(stmt)
