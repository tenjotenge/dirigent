import { useEffect, useRef } from "react";

import { ChatMessage } from "./ChatMessage";

import { ChatInput } from "./ChatInput";

import { WelcomeScreen } from "./WelcomeScreen";

import type { ChatMessage as ChatMessageType, WorkflowStatus } from "../types";

import { workflowStatusLabel } from "../utils/format";



interface CenterPanelProps {

  messages: ChatMessageType[];

  chatInput: string;

  onChatInputChange: (value: string) => void;

  onSend: () => void;

  isBusy: boolean;

  workflowStatus: WorkflowStatus;

  selectedModel: string;

  repoLoaded: boolean;

  onOpenRepository: () => void;

  isOpeningRepo: boolean;

}



export function CenterPanel({

  messages,

  chatInput,

  onChatInputChange,

  onSend,

  isBusy,

  workflowStatus,

  selectedModel,

  repoLoaded,

  onOpenRepository,

  isOpeningRepo,

}: CenterPanelProps) {

  const messagesEndRef = useRef<HTMLDivElement>(null);



  useEffect(() => {

    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });

  }, [messages, workflowStatus]);



  if (!repoLoaded) {

    return (

      <main className="center-panel">

        <WelcomeScreen

          onOpenRepository={onOpenRepository}

          isOpening={isOpeningRepo}

        />

      </main>

    );

  }



  return (

    <main className="center-panel">

      <div className="center-panel-header">

        <h2>Conversation</h2>

        {workflowStatus !== "idle" && (

          <div className={`workflow-status status-${workflowStatus}`}>

            <span className="workflow-spinner" />

            {workflowStatusLabel(workflowStatus)}

          </div>

        )}

      </div>



      <div className="chat-messages">

        {messages.length === 0 ? (

          <div className="empty-state">

            <p>Send a message to start working with Dirigent.</p>

            <p className="empty-state-hint">

              Model: {selectedModel || "none selected"}

            </p>

          </div>

        ) : (

          messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)

        )}

        <div ref={messagesEndRef} />

      </div>



      <ChatInput

        value={chatInput}

        onChange={onChatInputChange}

        onSend={onSend}

        disabled={isBusy || !selectedModel}

      />

    </main>

  );

}

