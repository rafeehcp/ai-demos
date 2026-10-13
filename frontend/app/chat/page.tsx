import type { Metadata } from "next";
import { ChatDemo } from "./ChatDemo";

export const metadata: Metadata = {
  title: "Chat with your docs",
  description: "Upload a PDF, ask questions, and get answers that cite the page they came from.",
};

export default function ChatPage() {
  return <ChatDemo />;
}
