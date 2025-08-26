# Database Design Best Practices for Scribe

## Core Principles

### 1. No Redundancy
- **Never store duplicate information** - wastes space and causes inconsistencies
- Each fact should be stored exactly once
- If you find yourself repeating data, create a separate table

### 2. Data Integrity
- Every piece of information must be accurate and complete
- Use constraints to enforce data validity
- Design prevents invalid states

### 3. Proper Normalization
- Apply First, Second, and Third Normal Forms
- No repeating groups or JSON arrays in columns
- All non-key columns depend only on the primary key

## The Design Process

### Step 1: Determine Database Purpose
For Scribe: "Internal mail management system for company employees to access shared mailboxes, manage permissions, and track mail operations with Azure AD integration."

### Step 2: Information Requirements
- User authentication via Azure AD
- Mail account connections
- Shared mailbox access control
- Session management
- Simple role-based permissions

### Step 3: Divide Into Tables
Each table represents ONE subject:
- Users (authentication entities)
- Sessions (active user sessions)
- Mail accounts (individual mailboxes)
- Shared mailboxes (company shared mailboxes)
- Access permissions (who can access what)

### Step 4: Column Design Rules
- **Smallest logical parts**: Split names, addresses into components
- **No calculated fields**: Don't store what can be computed
- **Single values only**: No arrays, lists, or JSON in columns
- **Factual data only**: Each column describes the table's subject

### Step 5: Primary Keys
- Use UUID/GUID for all primary keys
- Never use data that might change (names, emails)
- Ensure uniqueness and non-null values
- Consider AutoNumber/Identity columns

### Step 6: Relationships

#### One-to-Many
- Add foreign key to "many" side
- Example: user_id in sessions table

#### Many-to-Many
- Create junction table with both foreign keys
- Example: user_mailbox_access linking users and mailboxes

#### One-to-One
- Rare, consider combining tables
- If needed, share primary key

## Normalization Rules

### First Normal Form (1NF)
✅ Each cell contains single atomic value
✅ No repeating groups or arrays
✅ Each record is unique

**Violations to Fix:**
- No JSON columns for settings/permissions
- No comma-separated lists
- No numbered columns (field1, field2, etc.)

### Second Normal Form (2NF)
✅ Must be in 1NF
✅ Non-key columns depend on ENTIRE primary key
✅ No partial dependencies

**Example Fix:**
If table has composite key (user_id, mailbox_id), all other columns must depend on BOTH, not just one.

### Third Normal Form (3NF)
✅ Must be in 2NF
✅ No transitive dependencies
✅ Non-key columns independent of each other

**Example Fix:**
Don't store both birthdate and age - age depends on birthdate.

## Specific Rules for Scribe

### 1. No Multi-Value Columns
❌ BAD: permissions = '["read", "write", "delete"]'
✅ GOOD: Separate permission_types table with junction table

### 2. No Calculated Storage
❌ BAD: Storing unread_count, total_items
✅ GOOD: Calculate from actual messages when needed

### 3. Proper Entity Separation
❌ BAD: Users table with 30+ columns mixing auth, profile, preferences
✅ GOOD: Separate users, user_profiles, user_preferences tables

### 4. Consistent Naming
- Tables: plural, snake_case (users, mail_accounts)
- Columns: singular, snake_case (user_id, email_address)
- Foreign keys: tablename_id (user_id, mailbox_id)

### 5. Required Columns per Table
- id (UUID primary key)
- created_at (timestamp)
- updated_at (timestamp)
- Foreign keys as needed
- Core data fields only

## Implementation Checklist

- [ ] Each table represents ONE subject
- [ ] No duplicate data across tables
- [ ] All tables in Third Normal Form
- [ ] Proper primary keys (UUID)
- [ ] Clear foreign key relationships
- [ ] No JSON/array columns
- [ ] No calculated fields
- [ ] Consistent naming conventions
- [ ] Proper indexes on foreign keys
- [ ] Constraints enforce data integrity

## Current Schema Issues to Fix

### 1NF Violations:
- All JSON columns (extra_data, settings, permissions)
- Categories array in mail_message_cache
- Any comma-separated value fields

### 2NF Violations:
- Organization_id dependencies in junction tables
- Composite keys with partial dependencies

### 3NF Violations:
- Display names derived from first/last names
- Calculated counts stored alongside base data
- Status fields that depend on other status fields

### Redundancy Issues:
- Organization data repeated across tables
- User information duplicated in relationships
- Audit fields in every table (use central audit log)

## Migration Strategy

### Phase 1: Schema Creation
1. Create normalized tables
2. Establish proper constraints
3. Add necessary indexes

### Phase 2: Data Migration
1. Extract and clean existing data
2. Transform to normalized form
3. Migrate in dependency order

### Phase 3: Code Updates
1. Update SQLAlchemy models
2. Simplify repository layer
3. Adjust business logic
4. Update API endpoints

### Phase 4: Testing & Deployment
1. Test data integrity
2. Verify performance
3. Deploy with rollback plan
4. Monitor for issues

## Maintenance Best Practices

### Regular Reviews
- Check for new 1NF violations
- Look for redundant data creeping in
- Verify referential integrity
- Monitor query performance

### Change Management
- All schema changes require normalization review
- Document rationale for design decisions
- Maintain this document with updates
- Use migration scripts for all changes

---

*Last updated: $(date)*
*Version: 2.0 - Normalized Design*