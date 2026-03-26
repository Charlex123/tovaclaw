import type { ReactNode } from "react";
import FlightCard from "./FlightCard";
import ProductCard from "./ProductCard";
import { EmailDraftCard, EmailListCard } from "./EmailCard";
import TodoCard from "./TodoCard";
import EventCard from "./EventCard";
import OrderCard from "./OrderCard";
import EmergencyCard from "./EmergencyCard";
import ConfirmationCard from "./ConfirmationCard";
import NotesCard from "./NotesCard";
import FileCard from "./FileCard";
import CctvCard from "./CctvCard";
import FleetCard from "./FleetCard";
import CallCard from "./CallCard";

/* eslint-disable @typescript-eslint/no-explicit-any */
type CardRenderer = (data: any) => ReactNode;

const registry: Record<string, CardRenderer> = {
  flight_results: (data) => <FlightCard data={data} />,
  product_results: (data) => <ProductCard data={data} />,
  email_draft: (data) => <EmailDraftCard data={data} />,
  email_list: (data) => <EmailListCard data={data} />,
  todo_list: (data) => <TodoCard data={data} />,
  event_created: (data) => <EventCard data={data} />,
  order_history: (data) => <OrderCard data={data} />,
  order_status: (data) => <OrderCard data={data} />,
  emergency_alert: (data) => <EmergencyCard data={data} />,
  confirmation_needed: (data) => <ConfirmationCard data={data} />,
  notes_list: (data) => <NotesCard data={data} />,
  file_list: (data) => <FileCard data={data} />,
  cctv_status: (data) => <CctvCard data={data} />,
  fleet_status: (data) => <FleetCard data={data} />,
  call_status: (data) => <CallCard data={data} />,
};

export function renderActionCard(action: string, data: unknown): ReactNode {
  const renderer = registry[action];
  if (!renderer || !data) return null;
  return renderer(data);
}
