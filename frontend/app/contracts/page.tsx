import type { Metadata } from "next";
import { ContractsDemo } from "./ContractsDemo";

export const metadata: Metadata = {
  title: "Contract reviewer",
  description: "Upload a contract and get its key terms, clauses and risks, each backed by a quote checked against the document.",
};

export default function ContractsPage() {
  return <ContractsDemo />;
}
