# Setup Guide

Complete setup and installation guide for the Grizabella TypeScript API across different environments and platforms.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Setup](#environment-setup)
- [Configuration](#configuration)
- [Verification](#verification)
- [Platform-Specific Setup](#platform-specific-setup)
- [Development Environment](#development-environment)
- [Production Deployment](#production-deployment)

## Prerequisites

### System Requirements

**Minimum Requirements:**
- **Node.js**: 18.0.0 or higher
- **TypeScript**: 5.0.0 or higher
- **Memory**: 512 MB RAM
- **Disk Space**: 100 MB free space

**Recommended Requirements:**
- **Node.js**: 20.0.0 or higher
- **TypeScript**: 5.3.0 or higher
- **Memory**: 1 GB RAM
- **Disk Space**: 500 MB free space

### Required Software

1. **Node.js and npm**
   ```bash
   # Check if Node.js is installed
   node --version
   npm --version

   # If not installed, download from https://nodejs.org/
   ```

2. **TypeScript** (optional, will be installed as dev dependency)
   ```bash
   npm install -g typescript
   ```

3. **Git** (for cloning repositories)
   ```bash
   git --version
   ```

### Grizabella Server

Before using the TypeScript API, you need to have Grizabella installed. The TypeScript client automatically starts the MCP server using stdio transport, so you don't need to manually start a server.

```bash
# Install Grizabella Python package (required for MCP server)
pip install grizabella

# The TypeScript client will automatically start the server
# No manual server startup needed
```

**Important:** The TypeScript client uses stdio transport by default and automatically manages the MCP server lifecycle. You don't need to start a separate server process.

## Installation

### Option 1: Install from npm (Recommended)

```bash
# Create a new project
mkdir my-grizabella-app
cd my-grizabella-app
npm init -y

# Install the Grizabella TypeScript API
npm install grizabella-typescript-api decimal.js

# Install development dependencies
npm install -D typescript @types/node ts-node
```

### Option 2: Install from Source

```bash
# Clone the repository
git clone https://github.com/your-org/grizabella.git
cd grizabella/typescript

# Install dependencies
npm install

# Build the project
npm run build

# Use locally or link globally
npm link
```

### Option 3: Using Yarn

```bash
# Create a new project
yarn init -y

# Install the package
yarn add grizabella-typescript-api decimal.js

# Install development dependencies
yarn add -D typescript @types/node ts-node
```

## Environment Setup

### 1. Create Project Structure

```bash
# Create directories
mkdir -p src/{config,database,services,types,utils}
mkdir -p tests/{unit,integration}

# Create basic files
touch src/index.ts
touch src/config/database.ts
touch tests/basic.test.ts
```

### 2. Initialize TypeScript Configuration

Create `tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022"],
    "module": "CommonJS",
    "moduleResolution": "node",
    "declaration": true,
    "sourceMap": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "esModuleInterop": true,
    "skipLibCheck": false,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "types": ["node"]
  },
  "include": [
    "src/**/*"
  ],
  "exclude": [
    "node_modules",
    "dist",
    "tests"
  ]
}
```

### 3. Create Environment Configuration

Create `.env` file:

```bash
# Database Configuration
GRIZABELLA_DB_PATH=./data/my-database
GRIZABELLA_CREATE_IF_NOT_EXISTS=true

# Server Configuration
GRIZABELLA_SERVER_URL=http://localhost:8000/mcp

# Connection Settings
GRIZABELLA_TIMEOUT=30000
GRIZABELLA_DEBUG=false
GRIZABELLA_AUTO_RECONNECT=true

# Application Settings
NODE_ENV=development
LOG_LEVEL=info
```

Create `.env.example` for documentation:

```bash
# Copy this file to .env and fill in your values
GRIZABELLA_DB_PATH=./data/my-database
GRIZABELLA_CREATE_IF_NOT_EXISTS=true
GRIZABELLA_SERVER_URL=http://localhost:8000/mcp
GRIZABELLA_TIMEOUT=30000
GRIZABELLA_DEBUG=false
GRIZABELLA_AUTO_RECONNECT=true
NODE_ENV=development
LOG_LEVEL=info
```

### 4. Create Basic Application Files

**src/config/database.ts:**
```typescript
import { GrizabellaClientConfig, loadConfigFromEnv, validateConfig } from 'grizabella-typescript-api';

export function createDatabaseConfig(): GrizabellaClientConfig {
  // Load configuration from environment
  const config = loadConfigFromEnv();

  // Validate configuration
  const validation = validateConfig(config);
  if (!validation.isValid) {
    console.error('Configuration validation failed:');
    validation.errors.forEach(error => console.error(`  - ${error}`));
    throw new Error('Invalid configuration');
  }

  return config;
}
```

**src/index.ts:**
```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';
import { createDatabaseConfig } from './config/database';

async function main() {
  try {
    // Create configuration
    const config = createDatabaseConfig();

    // Create and connect client
    await using client = await GrizabellaClient.connect(config);

    console.log('✅ Connected to Grizabella successfully!');

    // Your application logic here
    await runApplication(client);

  } catch (error) {
    console.error('❌ Application failed:', error);
    process.exit(1);
  }
}

async function runApplication(client: GrizabellaClient) {
  // Test basic functionality
  const objectTypes = await client.listObjectTypes();
  console.log(`📋 Found ${objectTypes.length} object types`);

  // Add your application logic here
}

main().catch(console.error);
```

**package.json:**
```json
{
  "name": "my-grizabella-app",
  "version": "1.0.0",
  "description": "My Grizabella TypeScript application",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts",
    "test": "jest",
    "lint": "eslint src/**/*.ts",
    "clean": "rimraf dist"
  },
  "dependencies": {
    "grizabella-typescript-api": "^1.0.0",
    "decimal.js": "^10.4.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0",
    "ts-node": "^10.0.0",
    "jest": "^29.0.0",
    "eslint": "^8.0.0",
    "rimraf": "^5.0.0"
  },
  "keywords": ["grizabella", "typescript", "database"],
  "author": "Your Name",
  "license": "MIT"
}
```

## Configuration

### Basic Configuration

```typescript
import { GrizabellaClientConfig } from 'grizabella-typescript-api';

const basicConfig: GrizabellaClientConfig = {
  // Database configuration
  dbNameOrPath: './data/my-database',
  createIfNotExists: true,

  // Connection settings
  timeout: 30000,
  debug: false,
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,
  requestTimeout: 30000,
};

// Note: serverUrl defaults to 'stdio' and the client automatically starts the MCP server
```

### Environment-Based Configuration

```typescript
import { loadConfigFromEnv, buildConfig } from 'grizabella-typescript-api';

// Load from environment variables
const envConfig = loadConfigFromEnv();

// Build with defaults and overrides
const config = buildConfig({
  dbNameOrPath: process.env.GRIZABELLA_DB_PATH || './data/default-db',
  serverUrl: process.env.GRIZABELLA_SERVER_URL || 'http://localhost:8000/mcp',
  debug: process.env.NODE_ENV === 'development',
  timeout: parseInt(process.env.GRIZABELLA_TIMEOUT || '30000'),
});
```

### Advanced Configuration

```typescript
const advancedConfig: GrizabellaClientConfig = {
  dbNameOrPath: './data/my-database',
  createIfNotExists: true,

  // Advanced connection settings
  timeout: 30000,
  debug: true,
  autoReconnect: true,
  maxReconnectAttempts: 5,
  reconnectDelay: 1000,
  requestTimeout: 30000,

  // Custom retry configuration
  retryConfig: {
    maxRetries: 3,
    baseDelay: 1000,
    maxDelay: 5000,
    backoffMultiplier: 2,
    jitter: true,
  },
};

// Note: The client uses stdio transport by default and manages the MCP server automatically
```

## Verification

### 1. Test Installation

```bash
# Verify Node.js and npm
node --version
npm --version

# Check if package is installed
npm list grizabella-typescript-api

# Test import
node -e "const { GrizabellaClient } = require('grizabella-typescript-api'); console.log('✅ Import successful');"
```

### 2. Test Basic Functionality

Create `test-connection.ts`:

```typescript
import { GrizabellaClient } from 'grizabella-typescript-api';

async function testConnection() {
  try {
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: './data/test-db',
      createIfNotExists: true,
      debug: true,
    });

    console.log('✅ Connection successful!');

    // Test basic operations
    const objectTypes = await client.listObjectTypes();
    console.log(`📋 Object types: ${objectTypes.length}`);

    const relationTypes = await client.listRelationTypes();
    console.log(`🔗 Relation types: ${relationTypes.length}`);

    console.log('🎉 All tests passed!');

  } catch (error) {
    console.error('❌ Test failed:', error);
    process.exit(1);
  }
}

testConnection();
```

Run the test:

```bash
npx ts-node test-connection.ts
```

### 3. Test with Real Data

```typescript
import { GrizabellaClient, PropertyDataType } from 'grizabella-typescript-api';

async function testWithData() {
  await using client = await GrizabellaClient.connect({
    dbNameOrPath: './data/test-db',
    createIfNotExists: true,
  });

  // Create a test object type
  await client.createObjectType({
    name: 'TestUser',
    description: 'A test user object',
    properties: [
      {
        name: 'name',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
      },
      {
        name: 'email',
        data_type: PropertyDataType.TEXT,
        is_nullable: false,
        is_unique: true,
      },
      {
        name: 'age',
        data_type: PropertyDataType.INTEGER,
        is_nullable: true,
      },
    ],
  });

  console.log('✅ Created TestUser object type');

  // Create a test user
  const user = await client.upsertObject({
    id: 'test-user-1',
    object_type_name: 'TestUser',
    weight: new Decimal('1.0'),
    upsert_date: new Date(),
    properties: {
      name: 'Test User',
      email: 'test@example.com',
      age: 25,
    },
  });

  console.log('✅ Created test user:', user.properties.name);

  // Retrieve the user
  const retrievedUser = await client.getObjectById('test-user-1', 'TestUser');
  if (retrievedUser) {
    console.log('✅ Retrieved user:', retrievedUser.properties.name);
  }

  console.log('🎉 Data operations test completed successfully!');
}

testWithData().catch(console.error);
```

## Platform-Specific Setup

### macOS Setup

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Node.js
brew install node

# Install TypeScript
npm install -g typescript

# Install Python (for Grizabella server)
brew install python

# Start Grizabella server
python -m grizabella.mcp.server
```

### Windows Setup

```powershell
# Install Node.js from https://nodejs.org/

# Install TypeScript globally
npm install -g typescript

# Install Python from https://python.org/

# Start Grizabella server
python -m grizabella.mcp.server
```

Or using Chocolatey:

```powershell
# Install Chocolatey
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install Node.js
choco install nodejs

# Install Python
choco install python

# Install TypeScript
npm install -g typescript
```

### Linux Setup (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install TypeScript
npm install -g typescript

# Install Python
sudo apt install python3 python3-pip

# Install Grizabella
pip3 install grizabella

# Start Grizabella server
python3 -m grizabella.mcp.server
```

### Docker Setup

**Dockerfile:**
```dockerfile
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build TypeScript
RUN npm run build

# Expose port (if your app has a web server)
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  grizabella-app:
    build: .
    ports:
      - "3000:3000"
    environment:
      - GRIZABELLA_SERVER_URL=http://grizabella-server:8000/mcp
      - NODE_ENV=production
    depends_on:
      - grizabella-server

  grizabella-server:
    image: python:3.9
    command: python -m grizabella.mcp.server --host 0.0.0.0 --port 8000
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
```

**Build and run:**
```bash
# Build the application
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

## Development Environment

### VS Code Setup

1. **Install Extensions:**
   - TypeScript Hero
   - ESLint
   - Prettier
   - Auto Rename Tag

2. **VS Code Settings (.vscode/settings.json):**
   ```json
   {
     "typescript.preferences.importModuleSpecifier": "relative",
     "typescript.suggest.autoImports": true,
     "editor.formatOnSave": true,
     "editor.codeActionsOnSave": {
       "source.fixAll.eslint": true
     },
     "typescript.preferences.quoteStyle": "single",
     "typescript.format.semicolons": "insert"
   }
   ```

3. **Launch Configuration (.vscode/launch.json):**
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "Debug TypeScript",
         "type": "node",
         "request": "launch",
         "program": "${workspaceFolder}/src/index.ts",
         "outFiles": ["${workspaceFolder}/dist/**/*.js"],
         "preLaunchTask": "tsc: build - tsconfig.json",
         "sourceMaps": true
       }
     ]
   }
   ```

### Development Scripts

**package.json scripts:**
```json
{
  "scripts": {
    "dev": "ts-node --transpile-only src/index.ts",
    "dev:watch": "ts-node --transpile-only --watch src/index.ts",
    "build": "tsc",
    "build:watch": "tsc --watch",
    "start": "node dist/index.js",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "lint": "eslint src/**/*.ts",
    "lint:fix": "eslint src/**/*.ts --fix",
    "format": "prettier --write src/**/*.ts",
    "typecheck": "tsc --noEmit",
    "clean": "rimraf dist coverage",
    "prebuild": "npm run clean",
    "prepare": "npm run build"
  }
}
```

### Hot Reloading

```typescript
// src/dev-server.ts
import { spawn } from 'child_process';
import chokidar from 'chokidar';

class DevServer {
  private process: any;

  start() {
    this.startProcess();

    // Watch for file changes
    const watcher = chokidar.watch('src/**/*', {
      ignored: /node_modules/,
      persistent: true,
    });

    watcher.on('change', (path) => {
      console.log(`File changed: ${path}`);
      this.restart();
    });
  }

  private startProcess() {
    this.process = spawn('ts-node', ['src/index.ts'], {
      stdio: 'inherit',
      env: process.env,
    });

    this.process.on('exit', (code: number) => {
      if (code !== 0) {
        console.log('Process exited with code:', code);
      }
    });
  }

  private restart() {
    if (this.process) {
      this.process.kill();
    }
    setTimeout(() => this.startProcess(), 100);
  }
}

// Usage
if (process.env.NODE_ENV === 'development') {
  const devServer = new DevServer();
  devServer.start();
}
```

## Production Deployment

### Environment Variables

```bash
# Production environment variables
NODE_ENV=production
GRIZABELLA_DB_PATH=/data/production-database
GRIZABELLA_SERVER_URL=http://grizabella-server:8000/mcp
GRIZABELLA_CREATE_IF_NOT_EXISTS=false
GRIZABELLA_TIMEOUT=60000
GRIZABELLA_DEBUG=false
GRIZABELLA_AUTO_RECONNECT=true
LOG_LEVEL=warn
```

### Health Checks

```typescript
// src/health.ts
import { GrizabellaClient } from 'grizabella-typescript-api';

export async function healthCheck(): Promise<{
  status: 'healthy' | 'unhealthy';
  checks: Record<string, boolean>;
  timestamp: Date;
}> {
  const checks = {
    database: false,
    server: false,
    memory: false,
  };

  try {
    // Test database connectivity
    await using client = await GrizabellaClient.connect({
      dbNameOrPath: process.env.GRIZABELLA_DB_PATH!,
      serverUrl: process.env.GRIZABELLA_SERVER_URL!,
      timeout: 10000,
    });

    const objectTypes = await client.listObjectTypes();
    checks.database = true;
    checks.server = true;

    // Check memory usage
    const memoryUsage = process.memoryUsage();
    checks.memory = memoryUsage.heapUsed < 500 * 1024 * 1024; // 500MB

  } catch (error) {
    console.error('Health check failed:', error);
  }

  return {
    status: Object.values(checks).every(Boolean) ? 'healthy' : 'unhealthy',
    checks,
    timestamp: new Date(),
  };
}
```

### PM2 Configuration

**ecosystem.config.js:**
```javascript
module.exports = {
  apps: [{
    name: 'grizabella-app',
    script: 'dist/index.js',
    instances: 'max',
    exec_mode: 'cluster',
    env: {
      NODE_ENV: 'production',
      GRIZABELLA_DB_PATH: '/data/production-database',
      GRIZABELLA_SERVER_URL: 'http://localhost:8000/mcp',
    },
    error_file: './logs/err.log',
    out_file: './logs/out.log',
    log_file: './logs/combined.log',
    time: true,
  }],
};
```

### Docker Production Setup

**Dockerfile (Production):**
```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:20-alpine AS runtime

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user
RUN addgroup -g 1001 -S nodejs
RUN adduser -S app -u 1001

WORKDIR /app

# Copy built application
COPY --from=builder --chown=app:nodejs /app/node_modules ./node_modules
COPY --chown=app:nodejs . .

USER app

EXPOSE 3000

# Use dumb-init for proper signal handling
ENTRYPOINT ["dumb-init", "--"]
CMD ["npm", "start"]
```

### Monitoring

```typescript
// src/monitoring.ts
import { GrizabellaClient } from 'grizabella-typescript-api';

export class ApplicationMonitor {
  private client: GrizabellaClient;
  private metrics: Map<string, number> = new Map();

  constructor(client: GrizabellaClient) {
    this.client = client;
    this.startMetricsCollection();
  }

  private startMetricsCollection() {
    setInterval(async () => {
      try {
        // Collect database metrics
        const objectTypes = await this.client.listObjectTypes();
        this.metrics.set('object_types_count', objectTypes.length);

        const relationTypes = await this.client.listRelationTypes();
        this.metrics.set('relation_types_count', relationTypes.length);

        // Collect memory metrics
        const memoryUsage = process.memoryUsage();
        this.metrics.set('memory_heap_used', memoryUsage.heapUsed);
        this.metrics.set('memory_heap_total', memoryUsage.heapTotal);

      } catch (error) {
        console.error('Metrics collection failed:', error);
      }
    }, 30000); // Collect every 30 seconds
  }

  getMetrics(): Record<string, number> {
    return Object.fromEntries(this.metrics);
  }

  async getHealthStatus() {
    const metrics = this.getMetrics();
    const isHealthy = metrics.memory_heap_used < 800 * 1024 * 1024; // 800MB threshold

    return {
      status: isHealthy ? 'healthy' : 'unhealthy',
      metrics,
      timestamp: new Date(),
    };
  }
}
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Ensure Grizabella server is running
   python -m grizabella.mcp.server

   # Check if port is available
   lsof -i :8000
   ```

2. **TypeScript Compilation Errors**
   ```bash
   # Clean and rebuild
   npm run clean
   npm run build

   # Check TypeScript version
   npx tsc --version
   ```

3. **Memory Issues**
   ```bash
   # Increase Node.js memory limit
   node --max-old-space-size=4096 dist/index.js

   # Or set in package.json
   "start": "node --max-old-space-size=4096 dist/index.js"
   ```

4. **Import Errors**
   ```bash
   # Reinstall dependencies
   rm -rf node_modules package-lock.json
   npm install
   ```

### Getting Help

1. **Check Documentation**: Review this guide and API documentation
2. **Search Issues**: Check GitHub issues for similar problems
3. **Enable Debug Mode**: Set `GRIZABELLA_DEBUG=true` for detailed logs
4. **Community Support**: Join our community forum or Discord
5. **Professional Support**: Contact our support team for enterprise needs

## Next Steps

1. **Read the Examples**: Check out the comprehensive examples in the `examples/` directory
2. **Review Best Practices**: Read the best practices guide for production applications
3. **Explore API Reference**: See the complete API reference for detailed method documentation
4. **Join the Community**: Connect with other developers using Grizabella

Happy coding with Grizabella TypeScript API! 🚀