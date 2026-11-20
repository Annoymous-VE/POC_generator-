import type { ChatSession } from '../types';

export const INITIAL_DEMO_CHATS: ChatSession[] = [
  {
    id: 'demo-1',
    title: 'Cloud Migration Architecture',
    timestamp: 'Yesterday',
    isPinned: true,
    requirement: {
      type: 'document',
      fileName: 'AWS_Migration_RFP.pdf',
      fileSize: 420000,
    },
    messages: [
      {
        id: 'm1-1',
        sender: 'ai',
        content: "I've received AWS_Migration_RFP.pdf. We identified 3 core migration tracks: Database, Microservices, and IAM Federation.",
        timestamp: '10:15 AM',
      },
      {
        id: 'm1-2',
        sender: 'user',
        content: 'Can we prioritize Aurora PostgreSQL over DynamoDB for this POC phase?',
        timestamp: '10:18 AM',
      },
      {
        id: 'm1-3',
        sender: 'ai',
        content: 'Certainly! Aurora PostgreSQL aligns well with the existing relational data model and minimizes code refactoring.',
        timestamp: '10:19 AM',
      },
    ],
  },
  {
    id: 'demo-2',
    title: 'Healthcare Claims OCR',
    timestamp: '2 hours ago',
    isPinned: false,
    requirement: {
      type: 'image',
      fileName: 'Claim_Form_Sample.png',
      fileSize: 185000,
    },
    messages: [
      {
        id: 'm2-1',
        sender: 'ai',
        content: "I've analyzed Claim_Form_Sample.png. Key fields detected include Patient ID, Provider NPI, and ICD-10 diagnostic codes.",
        timestamp: '11:00 AM',
      },
      {
        id: 'm2-2',
        sender: 'user',
        content: 'Ensure we add human-in-the-loop review for confidence scores below 85%.',
        timestamp: '11:05 AM',
      },
    ],
  },
  {
    id: 'demo-3',
    title: 'Fintech Payment Routing',
    timestamp: '3 days ago',
    isPinned: false,
    requirement: {
      type: 'text',
      text: 'Design a resilient payment routing microservice supporting ACH, FedNow, and card rails with automatic fallback.',
    },
    messages: [
      {
        id: 'm3-1',
        sender: 'ai',
        content: "Received your fintech routing requirements. Let's design the state machine and failover circuit breaker.",
        timestamp: '03:45 PM',
      },
    ],
  },
];
