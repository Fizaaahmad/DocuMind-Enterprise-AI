export type User = { id: string; email: string; name: string };
export type Organization = {
  id: string;
  name: string;
  role: "admin" | "member";
};
export type Member = {
  user_id: string;
  email: string;
  name: string;
  role: "admin" | "member";
};
