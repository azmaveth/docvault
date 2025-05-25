# DocVault Threat Model

## Executive Summary

DocVault is a documentation management system that scrapes, stores, and searches technical documentation. This threat model identifies potential security risks, trust boundaries, and provides mitigation strategies for each identified threat.

## System Overview

### Core Components
1. **Web Scraper**: Fetches documentation from external URLs
2. **Document Storage**: SQLite database and file system storage
3. **Vector Search Engine**: Uses sqlite-vec for semantic search
4. **MCP Server**: Exposes functionality to AI assistants
5. **CLI Interface**: Command-line access to all features
6. **Embeddings Generation**: Uses Ollama for generating text embeddings

### Data Flow
1. User provides URL → Scraper fetches content → Processes HTML/Markdown → Stores in DB
2. User queries → Generate embeddings → Vector/text search → Return results
3. AI assistants → MCP server → Database operations → Return documentation

## Assets and Their Value

### High-Value Assets
1. **Documentation Database**
   - Contains scraped documentation from various sources
   - May include proprietary or sensitive technical information
   - Search history and usage patterns

2. **API Keys and Credentials**
   - Brave Search API key
   - Ollama connection details
   - Potential GitHub tokens for scraping

3. **Vector Embeddings**
   - Semantic representations of documentation
   - Could reveal information about indexed content

4. **User Configuration**
   - `.env` files with sensitive configuration
   - Database paths and storage locations

## Trust Boundaries

### External Trust Boundaries
1. **Internet → Web Scraper**: Untrusted content from external websites
2. **User Input → CLI**: Commands and parameters from users
3. **AI Assistants → MCP Server**: Requests from AI clients
4. **Ollama API → Embeddings Service**: External embedding generation

### Internal Trust Boundaries
1. **CLI → Database**: SQL queries and file operations
2. **MCP Server → Database**: API-mediated database access
3. **Scraper → Storage**: Content validation and sanitization

## Threat Analysis

### 1. Malicious URL Injection
**Threat**: Attacker provides malicious URLs to scraper
- **Attack Vector**: `dv add <malicious-url>`
- **Impact**: 
  - Server-Side Request Forgery (SSRF)
  - Access to internal network resources
  - Denial of Service through resource exhaustion
- **Likelihood**: High
- **Risk Level**: Critical

### 2. SQL Injection
**Threat**: Malicious input causes unintended SQL execution
- **Attack Vector**: Search queries, document IDs, filter parameters
- **Impact**:
  - Data exfiltration
  - Database corruption
  - Privilege escalation
- **Likelihood**: Medium (some parameterization exists)
- **Risk Level**: High

### 3. Path Traversal
**Threat**: Attacker accesses files outside intended directories
- **Attack Vector**: File paths in import/export commands
- **Impact**:
  - Access to sensitive system files
  - Overwriting critical files
  - Information disclosure
- **Likelihood**: Medium
- **Risk Level**: High

### 4. XSS via Stored Documentation
**Threat**: Malicious JavaScript in scraped content
- **Attack Vector**: Scraped HTML content displayed to users
- **Impact**:
  - Code execution in user context
  - Session hijacking (if web UI added)
  - Data theft
- **Likelihood**: Low (CLI-based, but MCP clients may render)
- **Risk Level**: Medium

### 5. Resource Exhaustion
**Threat**: Denial of service through resource consumption
- **Attack Vector**: 
  - Large depth parameter in scraping
  - Infinite redirect loops
  - Large document imports
- **Impact**:
  - System unavailability
  - Disk space exhaustion
  - Memory exhaustion
- **Likelihood**: High
- **Risk Level**: Medium

### 6. Insecure API Key Storage
**Threat**: Exposed API keys and credentials
- **Attack Vector**: 
  - Unencrypted `.env` files
  - Logs containing sensitive data
  - Git commits with credentials
- **Impact**:
  - Unauthorized API usage
  - Cost implications
  - Data access
- **Likelihood**: Medium
- **Risk Level**: High

### 7. MCP Server Authentication Bypass
**Threat**: Unauthorized access to MCP server endpoints
- **Attack Vector**: Direct HTTP requests to MCP server
- **Impact**:
  - Unauthorized documentation access
  - Database manipulation
  - Information disclosure
- **Likelihood**: High (no authentication implemented)
- **Risk Level**: Critical

### 8. Embedding Poisoning
**Threat**: Malicious content affects search results
- **Attack Vector**: Crafted documents designed to manipulate embeddings
- **Impact**:
  - Search result manipulation
  - Misdirection of users
  - Hidden content discovery
- **Likelihood**: Low
- **Risk Level**: Low

### 9. Command Injection
**Threat**: Shell command execution through user input
- **Attack Vector**: 
  - Git operations in scraper
  - File operations
  - External tool invocation
- **Impact**:
  - Arbitrary code execution
  - System compromise
  - Data exfiltration
- **Likelihood**: Medium
- **Risk Level**: Critical

### 10. Information Disclosure
**Threat**: Sensitive information exposed through various channels
- **Attack Vector**:
  - Error messages with stack traces
  - Debug logs
  - Verbose output modes
- **Impact**:
  - System information disclosure
  - Internal path disclosure
  - Configuration exposure
- **Likelihood**: High
- **Risk Level**: Medium

## Threat Mitigation Recommendations

### 1. URL Validation and SSRF Prevention

- **Implement URL allowlist** for trusted documentation sources
- **Validate URL schemes**: Only allow http/https
- **Implement request timeouts** and size limits
- **Block private IP ranges** (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8)
- **Use a proxy** for all external requests
- **Implement rate limiting** per domain

### 2. SQL Injection Prevention

- **Use parameterized queries exclusively** (partially implemented)
- **Implement query builders** or use SQLAlchemy ORM
- **Validate and sanitize** all user inputs
- **Use least-privilege database access**
- **Enable SQL query logging** for audit trails
- **Regular security audits** of database operations

### 3. Path Traversal Prevention

- **Validate all file paths** against allowed directories
- **Use `os.path.join()` and `realpath()` for path construction
- **Implement chroot-like restrictions** for file operations
- **Reject paths containing** `..`, `~`, or absolute paths
- **Use temporary directories** for processing

### 4. Content Security

- **Sanitize HTML content** before storage
- **Store content as plain text/markdown** when possible
- **Implement Content Security Policy** for any web interfaces
- **Escape content** when displaying to users
- **Use sandboxed rendering** for documentation preview

### 5. Resource Management

- **Implement scraping limits**:
  - Max depth: 5
  - Max pages per domain: 100
  - Max file size: 10MB
  - Request timeout: 30 seconds
- **Add disk space monitoring**
- **Implement queue-based scraping** with rate limits
- **Add memory usage limits** for processing

### 6. Secure Credential Management

- **Encrypt sensitive configuration** at rest
- **Use environment variables** for secrets (implemented)
- **Implement key rotation** procedures
- **Add `.env` to `.gitignore`** (verify)
- **Use secure key storage** (OS keychain integration)
- **Audit logs** for credential usage

### 7. MCP Server Security

- **Implement authentication**:
  - API key authentication
  - OAuth2 for AI assistants
  - Rate limiting per client
- **Use HTTPS only** for SSE transport
- **Implement CORS properly**
- **Add request validation** and sanitization
- **Log all API access**

### 8. Input Validation Framework

- **Create centralized validation**:

  ```python
  def validate_url(url: str) -> str:
      # Validate scheme, host, etc.
      pass
  
  def validate_search_query(query: str) -> str:
      # Sanitize search input
      pass
  
  def validate_file_path(path: str) -> str:
      # Ensure path safety
      pass
  ```

- **Use schema validation** for all inputs
- **Implement length limits** for all string inputs
- **Reject suspicious patterns** early

### 9. Security Headers and Configuration

- **Disable debug mode** in production
- **Implement security headers**:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Strict-Transport-Security
- **Use secure defaults** for all configuration
- **Implement least-privilege principle**

### 10. Monitoring and Auditing

- **Implement comprehensive logging**:
  - Authentication attempts
  - Data access patterns
  - Error conditions
  - Resource usage
- **Add intrusion detection**:
  - Unusual access patterns
  - Failed authentication spikes
  - Resource exhaustion attempts
- **Regular security audits**
- **Implement log rotation** and secure storage

## Implementation Priority

### Critical (Implement Immediately)

1. SQL injection prevention (complete parameterization)
2. MCP server authentication
3. URL validation and SSRF prevention
4. Path traversal prevention

### High (Implement Soon)

1. Resource limits and rate limiting
2. Secure credential management
3. Input validation framework
4. Command injection prevention

### Medium (Planned Improvements)

1. Content sanitization
2. Comprehensive logging
3. Security headers
4. Monitoring and alerting

## Security Testing Recommendations

1. **Automated Security Scanning**
   - Run `bandit` for Python security issues
   - Use `safety` to check dependencies
   - Implement SAST in CI/CD

2. **Manual Security Testing**
   - Attempt SSRF with various URL schemes
   - Test SQL injection on all inputs
   - Try path traversal attacks
   - Test resource exhaustion scenarios

3. **Dependency Management**
   - Regular dependency updates
   - Security advisory monitoring
   - License compliance checks

## Conclusion

DocVault's current architecture has several security vulnerabilities that need addressing. The most critical issues are:

1. Lack of authentication on the MCP server
2. Insufficient input validation across the application
3. Potential for SSRF attacks through the scraper
4. SQL injection risks in search functionality

Implementing the recommended mitigations in priority order will significantly improve the security posture of the application. Regular security audits and testing should be part of the development lifecycle.

## Implemented Mitigations

### Currently Implemented Security Measures (Updated 2025-05-25)

1. **Environment Variable Usage**
   - Sensitive configuration stored in `.env` files
   - API keys not hardcoded in source

2. **SQL Injection Prevention** ✅ **[FULLY IMPLEMENTED]**
   - Created `QueryBuilder` class for safe query construction
   - All dynamic queries now use parameterized statements
   - Removed string interpolation from SQL queries
   - Added SQL query logging for security auditing
   - Fixed vulnerabilities in:
     - `operations.py`: search_documents, get_library_versions
     - `version_commands.py`: versions_list_cmd, versions_check_cmd
     - All filter_clause usage replaced with safe parameterization

3. **Path Traversal Prevention** ✅ **[FULLY IMPLEMENTED]**
   - Created comprehensive `path_security.py` module with:
     - Path validation with null byte detection
     - Directory traversal pattern blocking
     - Symlink escape prevention
     - Filename sanitization
     - URL validation with SSRF protection
     - Archive member safety checks
   - Applied security measures to:
     - `storage.py`: save_html, save_markdown functions
     - `commands.py`: backup and restore operations
     - `scraper.py`: URL validation before fetching
     - `apply_migrations.py`: migration file validation
   - Comprehensive test suite for all security functions

4. **Content Type Storage**
   - Documents stored as markdown when possible
   - Some HTML sanitization during conversion

5. **Connection Security**
   - HTTPS URLs preferred for scraping
   - SSL/TLS for external API connections
   - URL validation prevents SSRF attacks on:
     - localhost/127.0.0.1
     - Private IP ranges (10.x, 192.168.x, 172.16-31.x)
     - Link-local addresses (169.254.x)
     - File:// and other dangerous URL schemes

6. **Error Handling**
   - Basic exception handling in place
   - Some error messages sanitized

## Security Implementation Checklist

### Critical Priority (Implement Immediately)

- [ ] ~~**MCP Server Authentication**~~ *(Deferred - local use only)*
  - [ ] ~~Implement API key authentication mechanism~~
  - [ ] ~~Add rate limiting per API key~~
  - [ ] ~~Create key management system~~
  - [ ] ~~Document authentication requirements~~

- [x] **Complete SQL Injection Prevention** ✅ *(Fully completed - 2025-05-25)*
  - [x] Audit all database queries for parameterization
  - [x] Replace string concatenation with parameterized queries
  - [x] Implement query builder or ORM
  - [x] Add SQL query logging for security audits
  - Notes: Fixed ALL SQL injection vulnerabilities. Created QueryBuilder class for safe query construction. All dynamic queries now use parameterized statements.

- [x] **URL Validation and SSRF Prevention** ✅ *(Fully completed - 2025-05-25)*
  - [x] Implement URL scheme validation (http/https only)
  - [x] Block private IP ranges (RFC 1918)
  - [x] Block localhost and link-local addresses
  - [x] Implement URL length limits (2048 chars)
  - [x] Add hostname validation
  - Notes: Comprehensive URL validation in path_security.py prevents SSRF attacks.

- [x] **Path Traversal Prevention** ✅ *(Fully completed - 2025-05-25)*
  - [x] Validate all file paths against allowed directories
  - [x] Use proper path resolution and validation
  - [x] Reject paths containing `..`, `~`, null bytes
  - [x] Implement file operation sandboxing
  - [x] Add archive member validation for zip files
  - Notes: Created path_security.py module with comprehensive validation. Applied to all file operations.

### High Priority (Implement Within 1 Week)

- [ ] **Command Injection Prevention**
  - [ ] Audit all subprocess/shell command usage
  - [ ] Use subprocess with shell=False
  - [ ] Validate and sanitize all command arguments
  - [ ] Implement command allowlisting

- [ ] **Resource Management**
  - [x] Set maximum scraping depth (5 levels)
  - [x] Limit pages per domain (100 pages)
  - [x] Add file size limits (10MB)
  - [x] Implement request timeouts (30 seconds)
  - [ ] Add concurrent request limits
  - Notes: Most limits implemented as part of SSRF prevention. Need to add explicit concurrent request limiting.

- [ ] **Input Validation Framework**
  - [ ] Create centralized validation module
  - [ ] Implement validators for URLs, queries, paths
  - [ ] Add length limits for all inputs
  - [ ] Create input sanitization utilities

- [ ] **Secure Credential Management**
  - [ ] Verify `.env` is in `.gitignore`
  - [ ] Document secure key rotation procedures
  - [ ] Consider OS keychain integration
  - [ ] Implement credential access logging

### Medium Priority (Implement Within 1 Month)

- [ ] **Content Security**
  - [ ] Implement HTML sanitization library
  - [ ] Add Content Security Policy headers
  - [ ] Create safe rendering context
  - [ ] Validate markdown conversion

- [ ] **Comprehensive Logging**
  - [ ] Implement structured logging
  - [ ] Add authentication attempt logging
  - [ ] Log all data access operations
  - [ ] Create log rotation policies
  - [ ] Secure log storage

- [ ] **Security Headers**
  - [ ] Add X-Content-Type-Options: nosniff
  - [ ] Add X-Frame-Options: DENY
  - [ ] Implement HSTS for HTTPS
  - [ ] Add security headers middleware

- [ ] **Error Handling Improvements**
  - [ ] Remove stack traces from production
  - [ ] Implement custom error pages
  - [ ] Add error rate monitoring
  - [ ] Create security incident procedures

### Low Priority (Planned Improvements)

- [ ] **Advanced Monitoring**
  - [ ] Implement anomaly detection
  - [ ] Add resource usage alerts
  - [ ] Create security dashboards
  - [ ] Set up automated alerts

- [ ] **Security Testing Integration**
  - [ ] Add `bandit` to CI/CD pipeline
  - [ ] Implement dependency scanning
  - [ ] Create security test suite
  - [ ] Schedule penetration testing

- [ ] **Documentation Security**
  - [ ] Create security guidelines
  - [ ] Document threat model updates
  - [ ] Maintain security changelog
  - [ ] Create incident response plan

- [ ] **Advanced Features**
  - [ ] Implement request signing
  - [ ] Add audit trail functionality
  - [ ] Create security metrics
  - [ ] Implement zero-trust architecture

## Progress Tracking

Use this section to track implementation progress:

- **Last Security Review**: 2025-05-25
- **Next Scheduled Review**: TBD
- **Security Issues Resolved**: 16
- **Pending Security Tasks**: 31

### Quick Wins Completed

- SQL injection prevention - ALL vulnerabilities fixed
- Implemented QueryBuilder for safe query construction
- Added SQL query logging capability
- Created SQL security audit script
- Path traversal prevention - comprehensive module created
- URL validation and SSRF prevention - fully implemented with:
  - Cloud metadata service blocking (AWS, GCP, Azure)
  - Private/reserved IP range blocking
  - Port blocking for internal services
  - Domain allowlist/blocklist support
  - URL length validation
- Request security controls implemented (as part of SSRF prevention):
  - Configurable timeout (default 30s)
  - Response size limits (default 10MB)
  - Depth limiting (default max 5)
  - Pages per domain limiting (default 100)
  - Proxy support for external requests
- Archive security validation - zip file safety checks
- Migration file validation - prevents malicious migrations

### In Progress

- Input validation framework
- Command injection prevention

### Blocked/Needs Discussion

- MCP Server Authentication (deferred for local use)
