import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MaskedSecretInput } from "@/components/settings/MaskedSecretInput";

describe("MaskedSecretInput", () => {
  it("never renders the secret value when connected (fingerprint only)", () => {
    render(
      <MaskedSecretInput
        label="OpenAI key"
        connected
        fingerprint="sk-…aB12 (3f9c)"
        editing={false}
        value="sk-supersecretvalue"
        onChange={() => {}}
      />,
    );

    // The connected affordance shows the fingerprint…
    expect(screen.getByText(/3f9c/)).toBeInTheDocument();
    // …but the secret value must NOT appear anywhere in the DOM.
    expect(screen.queryByText(/supersecret/)).not.toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain("sk-supersecretvalue");
    // No text input is rendered in the masked (connected, not editing) state.
    expect(screen.queryByDisplayValue("sk-supersecretvalue")).not.toBeInTheDocument();
  });

  it("uses a password input (masked) in the editing paste state", () => {
    const { container } = render(
      <MaskedSecretInput
        label="OpenAI key"
        connected={false}
        editing
        value="typed-key"
        onChange={() => {}}
      />,
    );
    const input = container.querySelector("input");
    expect(input).not.toBeNull();
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "off");
  });
});
