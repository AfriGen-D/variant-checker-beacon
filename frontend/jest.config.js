const nextJest = require('next/jest');

// Loads next.config.js and the SWC transform, so tests compile like the app.
const createJestConfig = nextJest({ dir: './' });

/** @type {import('jest').Config} */
module.exports = createJestConfig({
  testEnvironment: 'node',
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  testPathIgnorePatterns: ['<rootDir>/node_modules/', '<rootDir>/.next/', '<rootDir>/frontend/'],
});
