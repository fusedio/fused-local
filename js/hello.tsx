import React, { useState } from "react";

const HelloWorld: React.FC = () => {
    const [message, setMessage] = useState("Hello, world!");
    const [newMessage, setNewMessage] = useState("");

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setNewMessage(event.target.value);
    };

    const handleClick = () => {
        setMessage(newMessage);
        setNewMessage("");
    };

    return (
        <div>
            <h1>{message}</h1>
            <input type="text" value={newMessage} onChange={handleChange} />
            <button onClick={handleClick}>Change Message</button>
        </div>
    );
};

export default HelloWorld;
