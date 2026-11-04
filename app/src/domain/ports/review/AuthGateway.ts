export interface AuthUser {
  readonly uid: string;
  readonly email: string | null;
  readonly role: "admin" | "none";
}

export interface AuthGateway {
  isConfigured(): boolean;
  signIn(): Promise<AuthUser>;
  signOut(): Promise<void>;
  onAuthChange(callback: (user: AuthUser | null) => void, failed: (error: unknown) => void): () => void;
  idToken(): Promise<string | null>;
}
