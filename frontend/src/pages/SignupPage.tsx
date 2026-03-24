import SignupForm from "../components/auth/SignupForm";

const SignupPage = () => {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 text-center">
          Create Account
        </h1>
        <SignupForm />
      </div>
    </div>
  );
};

export default SignupPage;
