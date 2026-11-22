import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Card } from "../components/ui/Card";
import { Button, buttonClasses } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Alert } from "../components/ui/Alert";
import { evaluateEligibility, assistantTurn } from "../lib/api/client";
import type { EvaluateResponse, AssistantTurnResponse } from "../lib/api/types";
import { userMessageForCode } from "../lib/api/errors";

const STATES = [
  { value: "", label: "Select State / Union Territory" },
  { value: "IN-AP", label: "Andhra Pradesh" },
  { value: "IN-AR", label: "Arunachal Pradesh" },
  { value: "IN-AS", label: "Assam" },
  { value: "IN-BR", label: "Bihar" },
  { value: "IN-CT", label: "Chhattisgarh" },
  { value: "IN-DL", label: "Delhi (UT)" },
  { value: "IN-GA", label: "Goa" },
  { value: "IN-GJ", label: "Gujarat" },
  { value: "IN-HR", label: "Haryana" },
  { value: "IN-HP", label: "Himachal Pradesh" },
  { value: "IN-JH", label: "Jharkhand" },
  { value: "IN-KA", label: "Karnataka" },
  { value: "IN-KL", label: "Kerala" },
  { value: "IN-MP", label: "Madhya Pradesh" },
  { value: "IN-MH", label: "Maharashtra" },
  { value: "IN-MN", label: "Manipur" },
  { value: "IN-ML", label: "Meghalaya" },
  { value: "IN-MZ", label: "Mizoram" },
  { value: "IN-NL", label: "Nagaland" },
  { value: "IN-OR", label: "Odisha" },
  { value: "IN-PB", label: "Punjab" },
  { value: "IN-RJ", label: "Rajasthan" },
  { value: "IN-SK", label: "Sikkim" },
  { value: "IN-TN", label: "Tamil Nadu" },
  { value: "IN-TG", label: "Telangana" },
  { value: "IN-TR", label: "Tripura" },
  { value: "IN-UP", label: "Uttar Pradesh" },
  { value: "IN-UT", label: "Uttarakhand" },
  { value: "IN-WB", label: "West Bengal" },
];

const OCCUPATIONS = [
  { value: "", label: "Select Occupation" },
  { value: "farmer", label: "Farmer / Cultivator" },
  { value: "salaried", label: "Salaried employee" },
  { value: "self_employed", label: "Self-employed / Business" },
  { value: "daily_wage", label: "Daily wage worker" },
  { value: "unemployed", label: "Unemployed" },
  { value: "student", label: "Student" },
  { value: "homemaker", label: "Homemaker" },
  { value: "retired", label: "Retired" },
  { value: "other", label: "Other" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
];

const CATEGORIES = [
  { value: "", label: "All Categories" },
  { value: "general", label: "General" },
  { value: "obc", label: "OBC" },
  { value: "sc", label: "SC" },
  { value: "st", label: "ST" },
  { value: "ews", label: "EWS" },
  { value: "other", label: "Other" },
];

export function CheckEligibilityPage() {
  // The deterministic form works with no external-provider configuration.
  // Conversational mode is optional and can be unavailable when Groq is disabled.
  const [mode, setMode] = useState<"form" | "chat">("form");

  // Chat mode state
  const [userQuery, setUserQuery] = useState("");
  const [chatHistory, setChatHistory] = useState<Array<{ role: "user" | "assistant"; text: string }>>([]);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});

  // Direct form state
  const [formAge, setFormAge] = useState<number | "">("");
  const [formState, setFormState] = useState("");
  const [formOccupation, setFormOccupation] = useState("");
  const [formIncome, setFormIncome] = useState<number | "">("");
  const [formCategory, setFormCategory] = useState("");
  const [formIsFarmer, setFormIsFarmer] = useState("");
  const [formLandholding, setFormLandholding] = useState<number | "">("");
  const [formUnorganisedWorker, setFormUnorganisedWorker] = useState("");

  const [evaluationResult, setEvaluationResult] = useState<EvaluateResponse | null>(null);

  // Assistant turn mutation
  const assistantMutation = useMutation<
    AssistantTurnResponse,
    Error,
    { messages: string[]; answers: Record<string, unknown> }
  >({
    mutationFn: ({ messages, answers }) => assistantTurn({ messages, answers }),
    onSuccess: (data) => {
      setAnswers(data.extracted_profile);
      if (data.follow_up_question) {
        setChatHistory((prev) => [...prev, { role: "assistant", text: data.follow_up_question! }]);
      }
      if (data.eligibility_ready) {
        // Trigger auto evaluate
        evaluateMutation.mutate(data.extracted_profile);
      }
    },
  });

  // Evaluate mutation
  const evaluateMutation = useMutation<EvaluateResponse, Error, Record<string, unknown>>({
    mutationFn: (profileAnswers) => evaluateEligibility({ answers: profileAnswers }),
    onSuccess: (data) => {
      setEvaluationResult(data);
    },
  });

  const handleChatSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!userQuery.trim()) return;

    const newMessages = [...chatHistory.map((m) => m.text), userQuery.trim()];
    setChatHistory((prev) => [...prev, { role: "user", text: userQuery.trim() }]);
    setUserQuery("");

    assistantMutation.mutate({ messages: newMessages, answers });
  };

  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    const profileAnswers: Record<string, unknown> = {};
    if (formAge !== "") profileAnswers.age_years = Number(formAge);
    if (formState) profileAnswers.state_code = formState;
    if (formOccupation) profileAnswers.occupation = formOccupation;
    if (formIncome !== "") profileAnswers.annual_household_income_inr = Number(formIncome);
    if (formCategory) profileAnswers.social_category = formCategory;
    if (formIsFarmer) profileAnswers.is_farmer = formIsFarmer === "yes";
    if (formLandholding !== "") profileAnswers.landholding_acres = Number(formLandholding);
    if (formUnorganisedWorker) profileAnswers.is_unorganised_worker = formUnorganisedWorker === "yes";

    evaluateMutation.mutate(profileAnswers);
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold text-foreground">Find Government Schemes You May Qualify For</h1>
        <p className="max-w-prose text-muted">
          Describe your situation in plain language or use the quick form below. No login or Aadhaar required.
        </p>
      </header>

      <div className="flex items-center gap-2 border-b border-border pb-4">
        <Button
          variant={mode === "chat" ? "primary" : "secondary"}
          onClick={() => setMode("chat")}
        >
          Conversational Assistant
        </Button>
        <Button
          variant={mode === "form" ? "primary" : "secondary"}
          onClick={() => setMode("form")}
        >
          Direct Form
        </Button>
      </div>

      {mode === "chat" ? (
        <Card className="flex flex-col gap-6 p-6">
          <h2 className="text-xl font-semibold text-foreground">Tell us about yourself</h2>
          <p className="text-sm text-muted">
            For example: &quot;I am a 28 year old farmer from Andhra Pradesh with 2 acres of land and family income of ₹1.5 Lakh.&quot;
          </p>

          <div className="flex flex-col gap-4 rounded-[12px] bg-background p-4 min-h-[160px] max-h-[300px] overflow-y-auto">
            {chatHistory.length === 0 ? (
              <p className="text-sm text-muted italic">No conversation yet. Type your message below to start.</p>
            ) : (
              chatHistory.map((msg, i) => (
                <div
                  key={i}
                  className={`flex flex-col gap-1 p-3 rounded-[12px] max-w-[80%] ${
                    msg.role === "user"
                      ? "ml-auto bg-primary text-surface"
                      : "mr-auto bg-surface border border-border text-foreground"
                  }`}
                >
                  <span className="text-xs opacity-75">{msg.role === "user" ? "You" : "Assistant"}</span>
                  <p className="text-sm whitespace-pre-wrap">{msg.text}</p>
                </div>
              ))
            )}
          </div>

          {assistantMutation.isError && (
            <Alert tone="danger">
              The conversational assistant is unavailable. Use Direct Form to check eligibility without AI.
            </Alert>
          )}

          <form onSubmit={handleChatSubmit} className="flex gap-2">
            <input
              type="text"
              value={userQuery}
              onChange={(e) => setUserQuery(e.target.value)}
              placeholder="Describe your situation or answer the follow-up question..."
              className="min-h-11 flex-1 rounded-[12px] border border-border bg-surface px-4 text-sm text-foreground focus-visible:outline-3 focus-visible:outline-focus-ring"
              disabled={assistantMutation.isPending}
            />
            <Button type="submit" variant="primary" disabled={assistantMutation.isPending}>
              {assistantMutation.isPending ? "Thinking..." : "Send"}
            </Button>
          </form>
        </Card>
      ) : (
        <form onSubmit={handleFormSubmit} className="flex flex-col gap-6">
          <Card className="flex flex-col gap-6 p-6">
            <h2 className="text-xl font-semibold text-foreground">Basic Profile Answers</h2>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <Input
                label="Age (Years)"
                id="age"
                type="number"
                min={0}
                max={120}
                value={formAge}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setFormAge(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 35"
              />

              <Select
                label="State / Union Territory"
                id="state"
                value={formState}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormState(e.target.value)}
                options={STATES}
              />

              <Select
                label="Occupation"
                id="occupation"
                value={formOccupation}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormOccupation(e.target.value)}
                options={OCCUPATIONS}
              />

              <Select
                label="Social Category"
                id="category"
                value={formCategory}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormCategory(e.target.value)}
                options={CATEGORIES}
              />

              <Input
                label="Annual Household Income (INR)"
                id="income"
                type="number"
                min={0}
                value={formIncome}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setFormIncome(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 150000"
              />

              <Select
                label="Do you cultivate or own agricultural land?"
                id="is-farmer"
                value={formIsFarmer}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormIsFarmer(e.target.value)}
                options={[
                  { value: "", label: "Select an answer" },
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
              />

              <Input
                label="Agricultural Landholding (Acres)"
                id="landholding"
                type="number"
                min={0}
                step="0.01"
                value={formLandholding}
                onChange={(e: ChangeEvent<HTMLInputElement>) => setFormLandholding(e.target.value === "" ? "" : Number(e.target.value))}
                placeholder="e.g. 2.5"
              />

              <Select
                label="Do you work in the informal / unorganised sector?"
                id="unorganised-worker"
                value={formUnorganisedWorker}
                onChange={(e: ChangeEvent<HTMLSelectElement>) => setFormUnorganisedWorker(e.target.value)}
                options={[
                  { value: "", label: "Select an answer" },
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
              />
            </div>

            <Button type="submit" variant="primary" disabled={evaluateMutation.isPending} className="self-start">
              {evaluateMutation.isPending ? "Evaluating..." : "Evaluate Eligibility"}
            </Button>
          </Card>
        </form>
      )}

      {evaluateMutation.isError && (
        <Alert tone="danger">
          {userMessageForCode(evaluateMutation.error.message)}
        </Alert>
      )}

      {evaluationResult && (
        <section className="flex flex-col gap-6">
          <h2 className="text-2xl font-bold text-foreground">Matched Schemes ({evaluationResult.results.length})</h2>

          {evaluationResult.results.length === 0 ? (
            <Alert tone="info">
              No matching schemes found for your current profile answers. Try adjusting your inputs.
            </Alert>
          ) : (
            <div className="flex flex-col gap-4">
              {evaluationResult.results.map((res) => (
                <Card key={res.scheme_id} className="flex flex-col gap-4 p-6">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-xl font-bold text-foreground">{res.name}</h3>
                    <span
                      className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                        res.decision === "LIKELY_ELIGIBLE"
                          ? "bg-success-soft text-success"
                          : res.decision === "NEEDS_MORE_INFORMATION"
                          ? "bg-warning-soft text-warning"
                          : "bg-muted-soft text-muted"
                      }`}
                    >
                      {res.decision.replace(/_/g, " ")}
                    </span>
                  </div>

                  <div className="flex flex-col gap-2">
                    <p className="text-sm font-semibold text-foreground">Matching Criteria:</p>
                    <ul className="flex flex-col gap-1 text-sm text-muted">
                      {res.criteria.map((c) => (
                        <li key={c.criterion_id} className="flex items-center gap-2">
                          <span
                            className={
                              c.status === "PASS"
                                ? "text-success font-bold"
                                : c.status === "FAIL"
                                ? "text-danger font-bold"
                                : "text-warning font-bold"
                            }
                          >
                            [{c.status}]
                          </span>
                          <span>{c.explanation}</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  {res.document_checklist && res.document_checklist.length > 0 && (
                    <div className="flex flex-col gap-1">
                      <p className="text-sm font-semibold text-foreground">Documents Required:</p>
                      <p className="text-sm text-muted">
                        {res.document_checklist.map((d: any) => d?.name || d?.title || "Document").join(", ")}
                      </p>
                    </div>
                  )}

                  <div className="flex items-center gap-4 pt-2">
                    <Link to={`/schemes/${res.scheme_id}`} className={buttonClasses("secondary", "md")}>
                      View Scheme Details
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}

          <p className="text-xs text-muted italic border-t border-border pt-4">
            {evaluationResult.disclaimer}
          </p>
        </section>
      )}
    </div>
  );
}

export default CheckEligibilityPage;
