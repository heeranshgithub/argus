"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toApiError } from "@/lib/api-error";
import { sessionCreateSchema, type SessionCreateInput } from "@/schemas/session";
import { useCreateSessionMutation } from "@/services/sessions";

export function SessionCreateForm() {
  const router = useRouter();
  const [createSession, { isLoading }] = useCreateSessionMutation();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<SessionCreateInput>({
    resolver: zodResolver(sessionCreateSchema),
    defaultValues: { companyName: "", website: "", objective: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      const session = await createSession(values).unwrap();
      toast.success("Session created");
      router.push(`/sessions/${session.id}`);
    } catch (error) {
      const { message } = toApiError(error);
      toast.error("Could not create session", { description: message });
    }
  });

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="font-display text-2xl font-extrabold tracking-tight">
          Session brief
        </CardTitle>
        <CardDescription>
          Tell Argus who you&apos;re meeting and what you want to learn.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
          <div className="flex flex-col gap-2">
            <Label htmlFor="companyName">Company name</Label>
            <Input
              id="companyName"
              placeholder="Acme Corp"
              aria-invalid={!!errors.companyName}
              {...register("companyName")}
            />
            {errors.companyName && (
              <p className="text-sm text-destructive">
                {errors.companyName.message}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="website">Website</Label>
            <Input
              id="website"
              type="url"
              placeholder="https://acme.com"
              aria-invalid={!!errors.website}
              {...register("website")}
            />
            {errors.website && (
              <p className="text-sm text-destructive">{errors.website.message}</p>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="objective">Objective</Label>
            <Textarea
              id="objective"
              rows={5}
              placeholder="Understand their priorities and recent initiatives before the call."
              aria-invalid={!!errors.objective}
              {...register("objective")}
            />
            {errors.objective && (
              <p className="text-sm text-destructive">
                {errors.objective.message}
              </p>
            )}
          </div>

          <Button
            type="submit"
            size="lg"
            disabled={isLoading}
            className="mt-1 w-full sm:w-auto sm:self-start sm:px-8"
          >
            {isLoading && <Loader2 className="size-4 animate-spin" />}
            Create session
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
