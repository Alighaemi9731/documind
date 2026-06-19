/// <reference types="@testing-library/jest-dom" />

// Ensures the jest-dom matcher types (toBeInTheDocument, toHaveAttribute, …)
// are available to `tsc --noEmit` over the test files.
import "@testing-library/jest-dom";
