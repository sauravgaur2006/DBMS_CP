-- ============================================================
-- Automatic Index Recommendation — Dedicated MySQL User Setup
-- ============================================================
-- Run this ONCE as root:
--   mysql -u root -p < database/create_user.sql
--
-- IMPORTANT: Change the password below before running!
-- ============================================================

-- Drop the user if it already exists (ignore error if it doesn't)
DROP USER IF EXISTS 'indexrec_user'@'localhost';

-- Create the dedicated project user
CREATE USER 'indexrec_user'@'localhost' IDENTIFIED BY 'DBMS_CP';

-- Grant full access ONLY to the project database
GRANT ALL PRIVILEGES ON index_recommender.* TO 'indexrec_user'@'localhost';

FLUSH PRIVILEGES;
