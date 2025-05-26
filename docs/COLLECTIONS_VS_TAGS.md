# Collections vs Tags: A Guide to Organizing Your Documentation

DocVault provides two powerful ways to organize your documentation: **Tags** and **Collections**. Understanding the distinction between them will help you build a more effective documentation system.

## Quick Summary

- **Tags** = Descriptive attributes (like labels)
- **Collections** = Project groupings (like folders)

## Tags: Descriptive Attributes

Tags are **descriptive labels** that characterize what a document is about. Think of them as attributes or properties that help categorize and find documents.

### Characteristics of Tags
- Many-to-many relationship (documents can have multiple tags)
- Descriptive rather than organizational
- Great for cross-cutting concerns
- Ideal for search and filtering

### Examples of Good Tags
- `python`, `javascript`, `rust` (languages)
- `async`, `security`, `authentication` (topics)  
- `tutorial`, `reference`, `api` (document types)
- `beginner`, `advanced` (difficulty levels)
- `deprecated`, `experimental` (status)

### Using Tags
```bash
# Add tags to a document
dv tag add 123 python async security

# Search by tags
dv search --tags python security

# List documents with specific tags
dv tag list python
```

## Collections: Project Groupings

Collections are **curated sets of documents** organized for a specific purpose or project. Think of them as project folders or reading lists.

### Characteristics of Collections
- Documents can belong to multiple collections
- Purpose-driven organization
- Can maintain document order (learning paths)
- Include optional notes about why documents are included
- Can suggest default tags for consistency

### Examples of Good Collections
- "Building My SaaS App" (all docs for your current project)
- "Python Web Development" (Django + FastAPI + deployment docs)
- "Machine Learning Pipeline" (PyTorch + MLflow + Kubeflow)
- "Frontend Stack" (React + TypeScript + testing docs)
- "Security Best Practices" (curated security documentation)

### Using Collections
```bash
# Create a collection
dv collection create "My SaaS Project" --description "Docs for my startup"

# Add documents to collection
dv collection add "My SaaS Project" 123 456 789

# View collection contents
dv collection show "My SaaS Project"

# Search within a collection
dv search authentication --collection "My SaaS Project"
```

## When to Use Each

### Use Tags When...
- You want to describe what a document is about
- You need to find documents by topic/technology/type
- You're categorizing documents by their attributes
- You want flexible, cross-cutting organization

### Use Collections When...
- You're working on a specific project
- You need to group related documentation
- You want to maintain a learning path or reading order
- You're building a curated set for a purpose

## Power Combinations: Using Both Together

The real power comes from using tags and collections together. Here are some powerful patterns:

### 1. Project-Based Collections with Consistent Tagging
```bash
# Create a collection with suggested tags
dv collection create "FastAPI Microservice" --tags python fastapi microservices

# When adding docs, apply the suggested tags
dv collection add "FastAPI Microservice" 123
dv tag add 123 python fastapi microservices
```

### 2. Search Within Collections Using Tags
```bash
# Find all security-related docs in your project
dv search --collection "My SaaS Project" --tags security

# Find Python async docs in your web dev collection  
dv search --collection "Python Web Dev" --tags python async
```

### 3. Building Learning Paths
```bash
# Create a learning collection
dv collection create "Learn Django" --description "Django from basics to advanced"

# Add documents in learning order
dv collection add "Learn Django" 101  # Django basics
dv collection add "Learn Django" 102  # Models and ORM
dv collection add "Learn Django" 103  # Views and Templates
dv collection add "Learn Django" 104  # Advanced patterns

# Tag them appropriately
dv tag add 101 102 103 104 django python web beginner
dv tag add 104 advanced patterns
```

### 4. Multi-Project Document Sharing
```bash
# A security document can be in multiple project collections
dv collection add "Web App Project" 789
dv collection add "Mobile App Project" 789
dv collection add "Security Best Practices" 789

# And tagged for easy finding
dv tag add 789 security authentication oauth2
```

## Best Practices

### For Tags
1. **Be Consistent**: Use `python` not `Python` or `py`
2. **Be Specific**: Use `django-rest-framework` not just `django`
3. **Limit Quantity**: 3-7 tags per document is usually enough
4. **Create Tag Taxonomy**: Document your tag conventions

### For Collections
1. **Purpose-Driven Names**: "Django REST API Project" not "Docs"
2. **Add Descriptions**: Explain the collection's purpose
3. **Use Default Tags**: Set suggested tags for consistency
4. **Maintain Order**: For learning paths, position matters
5. **Regular Cleanup**: Archive inactive project collections

### Combined Strategies
1. **Tag First, Collect Second**: Tag documents as you add them, then organize into collections
2. **Collection Templates**: Create standard collections with default tags for common project types
3. **Cross-Reference**: Use tags to find candidates for collections
4. **Regular Reviews**: Periodically review both tags and collections for cleanup

## Example Workflows

### Starting a New Project
```bash
# 1. Create a project collection
dv collection create "E-commerce Platform" \
  --description "Next.js + Stripe + PostgreSQL" \
  --tags nextjs react stripe postgresql

# 2. Search and add relevant docs
dv search nextjs --limit 10
dv collection add "E-commerce Platform" 234 235 236

dv search "stripe api"
dv collection add "E-commerce Platform" 345

# 3. Apply consistent tags
dv tag add 234 235 236 345 e-commerce project-x
```

### Research Phase
```bash
# Use tags to explore options
dv search --tags python "web framework" --limit 20

# Create a research collection
dv collection create "Web Framework Comparison"

# Add candidates to compare
dv collection add "Web Framework Comparison" 123 456 789
```

### Building a Knowledge Base
```bash
# Create topic-based collections
dv collection create "Security Knowledge Base"
dv collection create "Performance Optimization"
dv collection create "Testing Best Practices"

# Use tags to find and categorize
dv search --tags security | # Find all security docs
dv collection add "Security Knowledge Base" <ids>
```

## Summary

- **Tags** = What it's about (descriptive)
- **Collections** = What it's for (organizational)
- **Together** = Powerful documentation management

Use tags liberally to describe your documents, and create collections thoughtfully to organize them for your specific needs. The combination gives you both flexible search capabilities and purposeful organization.