import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "@/components/ui/Modal";

function Harness({ onClose }: { onClose: () => void }) {
  return (
    <Modal open onClose={onClose} title="Confirm" description="Are you sure?">
      <button type="button">First</button>
      <button type="button">Second</button>
    </Modal>
  );
}

describe("Modal", () => {
  it("renders as an accessible dialog labelled + described by its content", () => {
    render(<Harness onClose={() => {}} />);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    // Name/description come from aria-labelledby/aria-describedby (the visible
    // title + description), so they are programmatically associated, not just
    // a duplicated aria-label string.
    expect(dialog).toHaveAccessibleName("Confirm");
    expect(dialog).toHaveAccessibleDescription("Are you sure?");
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("traps focus: Tab from the last focusable wraps to the first", async () => {
    render(<Harness onClose={() => {}} />);
    const first = screen.getByRole("button", { name: "First" });
    const second = screen.getByRole("button", { name: "Second" });
    // Let the modal's deferred initial focus settle before exercising the trap,
    // so it doesn't race the Tab we fire below.
    await waitFor(() => expect(first).toHaveFocus());

    second.focus();
    expect(second).toHaveFocus();

    await userEvent.tab();
    expect(first).toHaveFocus();
  });

  it("Shift+Tab from the first focusable wraps to the last", async () => {
    render(<Harness onClose={() => {}} />);
    const first = screen.getByRole("button", { name: "First" });
    const second = screen.getByRole("button", { name: "Second" });
    await waitFor(() => expect(first).toHaveFocus());

    first.focus();
    await userEvent.tab({ shift: true });
    expect(second).toHaveFocus();
  });
});
