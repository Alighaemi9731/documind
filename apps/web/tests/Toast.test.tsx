import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ToastProvider, useToast } from "@/components/ui/Toast";

function Trigger() {
  const toast = useToast();
  return (
    <button type="button" onClick={() => toast.success("Saved!")}>
      go
    </button>
  );
}

describe("Toast", () => {
  it("shows a toast when pushed and dismisses it on the close button", async () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: "go" }));
    expect(screen.getByText("Saved!")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(screen.queryByText("Saved!")).not.toBeInTheDocument();
  });

  it("throws when useToast is used outside the provider", () => {
    function Orphan() {
      useToast();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow(/ToastProvider/);
  });
});
