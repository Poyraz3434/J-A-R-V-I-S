import { ATLAS_CONFIG } from "./config";
import { delay, Logger } from "./utils";

export type VerificationStatus = "pending" | "verified" | "failed";

export interface VerificationState {
  isRequired: boolean;
  challengeId: string;
  message: string;
  widgetVisible: boolean;
  status: VerificationStatus;
  attempts: number;
  startedAt: number;
  lastCheckedAt: number;
  userInput?: string;
}

export interface VerificationWidgetView {
  title: string;
  instructions: string[];
  inputPlaceholder: string;
  visible: boolean;
}

export class VerificationSystem {
  private state: VerificationState = {
    isRequired: false,
    challengeId: "",
    message: "",
    widgetVisible: false,
    status: "pending",
    attempts: 0,
    startedAt: 0,
    lastCheckedAt: 0,
  };

  private waiter?: {
    resolve: (value: boolean) => void;
    reject: (reason?: unknown) => void;
  };

  private pollHandle?: ReturnType<typeof setInterval>;

  startChallenge(): Promise<boolean> {
    this.state = {
      isRequired: true,
      challengeId: `atlas-${Date.now()}`,
      message: "⚠️ Robot Doğrulaması Gerekli - Lütfen Aşağıdaki Talimatları Takip Edin",
      widgetVisible: true,
      status: "pending",
      attempts: 0,
      startedAt: Date.now(),
      lastCheckedAt: Date.now(),
    };

    return new Promise<boolean>((resolve, reject) => {
      this.waiter = { resolve, reject };
      this.startPolling();
    });
  }

  public getWidgetView(): VerificationWidgetView {
    return {
      title: "⚠️ Robot Doğrulaması Gerekli",
      instructions: [
        "İşlemi gerçekleştirmek için ekrandaki talimatları takip edin.",
        "Doğrulama alanını doldurun ve onaylayın.",
        "Doğrulama 1 saniyede bir otomatik olarak kontrol edilir.",
      ],
      inputPlaceholder: "Doğrulama kodunu veya adımını girin",
      visible: this.state.widgetVisible,
    };
  }

  submitUserInput(value: string): void {
    if (!this.state.isRequired) {
      return;
    }

    this.state.userInput = value.trim();
    this.state.lastCheckedAt = Date.now();
    this.state.attempts += 1;

    if (this.state.userInput.length > 0) {
      this.validateAnswer();
    }
  }

  private startPolling(): void {
    this.pollHandle = setInterval(() => {
      this.state.lastCheckedAt = Date.now();

      if (this.state.status === "verified") {
        this.finishSuccess();
        return;
      }

      if (this.state.status === "failed") {
        Logger.warn("Verification failed. Please retry the operation.");
        this.finishFailure();
      }
    }, ATLAS_CONFIG.confirmationPollMs);
  }

  private validateAnswer(): void {
    const normalized = this.state.userInput?.toLowerCase() ?? "";
    const isValid = normalized.includes("verify") || normalized.includes("onay") || normalized.includes("continue");

    if (isValid) {
      this.state.status = "verified";
      this.state.widgetVisible = false;
      this.state.message = "Doğrulama başarılı. İşlem otomatik olarak devam ettiriliyor.";
      return;
    }

    this.state.status = "failed";
    this.state.message = "Lütfen işlemi tekrar deneyin";
  }

  private finishSuccess(): void {
    if (this.pollHandle) {
      clearInterval(this.pollHandle);
      this.pollHandle = undefined;
    }

    if (this.waiter) {
      this.waiter.resolve(true);
      this.waiter = undefined;
    }

    this.state.isRequired = false;
    this.state.widgetVisible = false;
  }

  private finishFailure(): void {
    if (this.pollHandle) {
      clearInterval(this.pollHandle);
      this.pollHandle = undefined;
    }

    if (this.waiter) {
      this.waiter.resolve(false);
      this.waiter = undefined;
    }

    this.state.isRequired = false;
    this.state.widgetVisible = false;
  }
}
