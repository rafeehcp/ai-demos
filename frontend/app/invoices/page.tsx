import type { Metadata } from "next";
import { InvoicesDemo } from "./InvoicesDemo";

export const metadata: Metadata = {
  title: "Invoice → JSON",
  description: "Turn invoices and receipts into structured data, with the arithmetic checked, ready to download as CSV or JSON.",
};

export default function InvoicesPage() {
  return <InvoicesDemo />;
}
