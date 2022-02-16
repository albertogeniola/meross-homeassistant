export interface ServiceStatus {
  readonly name: string;
  readonly status: string;
  readonly exit_code: number;
  readonly pid: number;
}
