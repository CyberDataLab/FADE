export interface UserPatch{
    username: string;
    old_password: string;
    new_password: string;
    confirm_new_password: string;
    email: string;
  }