import { initializeApp, type FirebaseApp } from "@firebase/app";
import { connectAuthEmulator, getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, type Auth,
  type User } from "@firebase/auth";
import type { AuthGateway, AuthUser } from "../../domain/ports/review/AuthGateway.ts";

export interface FirebaseWebConfig {
  readonly apiKey: string;
  readonly authDomain: string;
  readonly projectId: string;
  readonly appId: string;
  readonly emulator?: string;
}

export class FirebaseAuthGateway implements AuthGateway {
  private auth: Auth | null = null;

  constructor(private readonly config: FirebaseWebConfig | null) {}

  isConfigured(): boolean {
    return this.config !== null;
  }

  private connected(): Auth {
    if (!this.config) throw new Error("Firebase Auth is not configured for this build");
    if (!this.auth) {
      const app: FirebaseApp = initializeApp(this.config);
      this.auth = getAuth(app);
      if (this.config.emulator) connectAuthEmulator(this.auth, this.config.emulator, { disableWarnings: true });
    }
    return this.auth;
  }

  private async read(user: User): Promise<AuthUser> {
    const token = await user.getIdTokenResult();
    return { uid: user.uid, email: user.email, role: token.claims.admin === true ? "admin" : "none" };
  }

  async signIn(): Promise<AuthUser> {
    return this.read((await signInWithPopup(this.connected(), new GoogleAuthProvider())).user);
  }

  async signOut(): Promise<void> {
    await this.auth?.signOut();
  }

  onAuthChange(callback: (user: AuthUser | null) => void, failed: (error: unknown) => void): () => void {
    if (!this.config) {
      callback(null);
      return () => undefined;
    }
    const changed = (user: User | null) => {
      if (user) return void this.read(user).then(callback, failed);
      callback(null);
    };
    return onAuthStateChanged(this.connected(), changed);
  }

  async idToken(): Promise<string | null> {
    return this.auth?.currentUser ? this.auth.currentUser.getIdToken() : null;
  }
}
