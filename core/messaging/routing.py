EXCHANGE_NAME = "crm.topic"
EXCHANGE_TYPE = "topic"

QUEUE_LEADS_INGEST = "crm.leads.ingest"
QUEUE_LEADS_LLM_TAGGING = "crm.leads.llm_tagging"
QUEUE_AI_TAG_REQUESTED = "crm.ai.tag_requested"
QUEUE_ACTIONS_PROCESS = "crm.actions.process"
QUEUE_COMPANIES_SYNC = "crm.companies.sync"
QUEUE_DEADLETTER = "crm.deadletter"

ROUTING_KEYS = {
    QUEUE_LEADS_INGEST: ["lead.created.*", "lead.scraped.*", "lead.updated.*"],
    QUEUE_LEADS_LLM_TAGGING: ["lead.saved.*"],
    QUEUE_AI_TAG_REQUESTED: ["lead.tag_requested"],
    QUEUE_ACTIONS_PROCESS: ["action.logged.*"],
    QUEUE_COMPANIES_SYNC: ["company.created.*", "company.updated.*"],
}

QUEUES_CONFIG = {
    QUEUE_LEADS_INGEST: {
        "routing_keys": ROUTING_KEYS[QUEUE_LEADS_INGEST],
        "durable": True,
    },
    QUEUE_LEADS_LLM_TAGGING: {
        "routing_keys": ROUTING_KEYS[QUEUE_LEADS_LLM_TAGGING],
        "durable": True,
    },
    QUEUE_AI_TAG_REQUESTED: {
        "routing_keys": ROUTING_KEYS[QUEUE_AI_TAG_REQUESTED],
        "durable": True,
    },
    QUEUE_ACTIONS_PROCESS: {
        "routing_keys": ROUTING_KEYS[QUEUE_ACTIONS_PROCESS],
        "durable": True,
    },
    QUEUE_COMPANIES_SYNC: {
        "routing_keys": ROUTING_KEYS[QUEUE_COMPANIES_SYNC],
        "durable": True,
    },
    QUEUE_DEADLETTER: {
        "routing_keys": ["#"],
        "durable": True,
    },
}
