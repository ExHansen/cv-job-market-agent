import {
  Bot,
  BriefcaseBusiness,
  Building2,
  Database,
  FileUser,
  Kanban,
  type LucideIcon,
  MessageSquare,
  Radar,
  Sparkles,
} from "lucide-react";

export type NavBadge = "new" | "updated" | "soon";

export interface NavSubItem {
  id: string;
  title: string;
  url: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

interface NavItemBase {
  id: string;
  title: string;
  icon?: LucideIcon;
  badge?: NavBadge;
  disabled?: boolean;
  newTab?: boolean;
}

export interface NavMainLinkItem extends NavItemBase {
  url: string;
  subItems?: never;
}

export interface NavMainParentItem extends NavItemBase {
  subItems: NavSubItem[];
}

export type NavMainItem = NavMainLinkItem | NavMainParentItem;

export interface NavGroup {
  id: number;
  label?: string;
  items: NavMainItem[];
}

export const sidebarItems: NavGroup[] = [
  {
    id: 1,
    label: "CareerOS AI Studio",
    items: [
      {
        id: "assistant",
        title: "AI Copilot Chat",
        url: "/dashboard/assistant",
        icon: Bot,
      },
      {
        id: "job-finder",
        title: "Job Finder & HR Radar",
        url: "/dashboard/job-finder",
        icon: BriefcaseBusiness,
        badge: "new",
      },
      {
        id: "cv-studio",
        title: "CV & Company Studio",
        url: "/dashboard/cv-studio",
        icon: Sparkles,
      },
      {
        id: "company-intel",
        title: "Company Deep-Dive",
        url: "/dashboard/company-intel",
        icon: Building2,
      },
      {
        id: "company-database",
        title: "Company Knowledge DB",
        url: "/dashboard/company-database",
        icon: Database,
        badge: "new",
      },
      {
        id: "market-radar",
        title: "Job Market Radar",
        url: "/dashboard/market-radar",
        icon: Radar,
      },
      {
        id: "master-profile",
        title: "Master Profile",
        url: "/dashboard/master-profile",
        icon: FileUser,
      },
    ],
  },
  {
    id: 2,
    label: "Job Hunt Workspace",
    items: [
      {
        id: "applications",
        title: "Application Tracker",
        url: "/dashboard/applications",
        icon: Kanban,
      },
      {
        id: "interview-prep",
        title: "Interview Prep Chat",
        url: "/dashboard/interview-prep",
        icon: MessageSquare,
      },
    ],
  },
];
