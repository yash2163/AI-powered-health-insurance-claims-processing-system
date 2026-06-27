import os
import sqlite3
import json
from datetime import date
from typing import Optional, List, Dict, Any

from app.config import DATABASE_PATH
from app.models.claim import ClaimSubmission, ClaimHistoryEntry, ClaimDocument
from app.models.trace import ClaimDecision, AuditTrace, TraceStep
from app.models.enums import ClaimCategory

def init_db() -> None:
    """Create tables if they do not exist."""
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create claims table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS claims (
        claim_id TEXT PRIMARY KEY,
        member_id TEXT NOT NULL,
        policy_id TEXT NOT NULL,
        claim_category TEXT NOT NULL,
        treatment_date TEXT NOT NULL,
        claimed_amount REAL NOT NULL,
        hospital_name TEXT,
        submission_date TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    );
    """)
    
    # Create decisions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS decisions (
        claim_id TEXT PRIMARY KEY,
        decision TEXT NOT NULL,           -- APPROVED, PARTIAL, REJECTED, MANUAL_REVIEW
        approved_amount REAL,
        claimed_amount REAL NOT NULL,
        confidence_score REAL NOT NULL,
        message TEXT NOT NULL,
        rejection_reasons TEXT,           -- JSON array as text
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
    );
    """)
    
    # Create traces table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS traces (
        claim_id TEXT PRIMARY KEY,
        trace_json TEXT NOT NULL,         -- Full AuditTrace serialized as JSON
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (claim_id) REFERENCES claims(claim_id)
    );
    """)
    
    conn.commit()
    conn.close()

def save_claim(claim: ClaimSubmission) -> None:
    """Save a claim submission to the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO claims (claim_id, member_id, policy_id, claim_category, treatment_date, claimed_amount, hospital_name, submission_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(claim_id) DO UPDATE SET
        member_id=excluded.member_id,
        policy_id=excluded.policy_id,
        claim_category=excluded.claim_category,
        treatment_date=excluded.treatment_date,
        claimed_amount=excluded.claimed_amount,
        hospital_name=excluded.hospital_name,
        submission_date=excluded.submission_date
    """, (
        claim.claim_id,
        claim.member_id,
        claim.policy_id,
        claim.claim_category.value,
        claim.treatment_date.isoformat(),
        claim.claimed_amount,
        claim.hospital_name,
        claim.submission_date.isoformat()
    ))
    conn.commit()
    conn.close()

def save_decision(decision: ClaimDecision) -> None:
    """Save a claim decision and its trace to the database."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Save to decisions table
    cursor.execute("""
    INSERT INTO decisions (claim_id, decision, approved_amount, claimed_amount, confidence_score, message, rejection_reasons)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(claim_id) DO UPDATE SET
        decision=excluded.decision,
        approved_amount=excluded.approved_amount,
        claimed_amount=excluded.claimed_amount,
        confidence_score=excluded.confidence_score,
        message=excluded.message,
        rejection_reasons=excluded.rejection_reasons
    """, (
        decision.claim_id,
        decision.decision,
        decision.approved_amount,
        decision.claimed_amount,
        decision.confidence_score,
        decision.message,
        json.dumps(decision.rejection_reasons)
    ))
    
    # Save to traces table
    cursor.execute("""
    INSERT INTO traces (claim_id, trace_json)
    VALUES (?, ?)
    ON CONFLICT(claim_id) DO UPDATE SET
        trace_json=excluded.trace_json
    """, (
        decision.claim_id,
        decision.trace.model_dump_json()
    ))
    
    conn.commit()
    conn.close()

def get_all_decisions() -> List[Dict[str, Any]]:
    """Retrieve all decisions with their claim details."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.claim_id, d.decision, d.approved_amount, d.claimed_amount, d.confidence_score, d.message, d.rejection_reasons, d.created_at,
           c.member_id, c.policy_id, c.claim_category, c.treatment_date, c.hospital_name, c.submission_date
    FROM decisions d
    JOIN claims c ON d.claim_id = c.claim_id
    ORDER BY d.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        item = dict(r)
        item["rejection_reasons"] = json.loads(item["rejection_reasons"]) if item["rejection_reasons"] else []
        result.append(item)
    return result

def get_decision(claim_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a single decision and its trace by claim ID."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.claim_id, d.decision, d.approved_amount, d.claimed_amount, d.confidence_score, d.message, d.rejection_reasons, d.created_at,
           c.member_id, c.policy_id, c.claim_category, c.treatment_date, c.hospital_name, c.submission_date,
           t.trace_json
    FROM decisions d
    JOIN claims c ON d.claim_id = c.claim_id
    LEFT JOIN traces t ON d.claim_id = t.claim_id
    WHERE d.claim_id = ?
    """, (claim_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    item = dict(row)
    item["rejection_reasons"] = json.loads(item["rejection_reasons"]) if item["rejection_reasons"] else []
    item["trace"] = json.loads(item["trace_json"]) if item["trace_json"] else None
    return item

def get_claims_for_member(member_id: str) -> List[Dict[str, Any]]:
    """Retrieve all claims submitted by a member."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
    SELECT claim_id, member_id, policy_id, claim_category, treatment_date, claimed_amount, hospital_name, submission_date, created_at
    FROM claims
    WHERE member_id = ?
    ORDER BY created_at DESC
    """, (member_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
